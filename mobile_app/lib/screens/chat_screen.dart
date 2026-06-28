import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:permission_handler/permission_handler.dart';
import 'dart:ui' as ui;
import '../services/chat_provider.dart';
import '../widgets/message_bubble.dart';
import '../widgets/app_chrome.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen>
    with SingleTickerProviderStateMixin {
  final TextEditingController _textController = TextEditingController();
  final stt.SpeechToText _speech = stt.SpeechToText();
  bool _speechAvailable = false;
  bool _isListening = false;

  /// True from mic tap-start until tap-stop finishes (plugin may stop early).
  bool _micSessionOpen = false;
  String? _localeId;
  String _lastRecognizedWords = '';
  AnimationController? _pulseController;
  Animation<double>? _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
    _pulseAnimation = Tween<double>(begin: 1.0, end: 1.12).animate(
      CurvedAnimation(parent: _pulseController!, curve: Curves.easeInOut),
    );
    _initSpeech();
  }

  @override
  void dispose() {
    _micSessionOpen = false;
    _speech.stop();
    _pulseController?.dispose();
    _textController.dispose();
    super.dispose();
  }

  void _initSpeech() async {
    await Permission.microphone.request();
    _speechAvailable = await _speech.initialize(
      onStatus: _onSpeechStatus,
      onError: _onSpeechError,
    );
    if (_speechAvailable) {
      final locales = await _speech.locales();
      if (locales.isNotEmpty) {
        final deviceLanguage =
            ui.PlatformDispatcher.instance.locale.languageCode;
        final preferred = locales.where(
          (l) =>
              l.localeId.toLowerCase().startsWith(deviceLanguage.toLowerCase()),
        );
        _localeId = preferred.isNotEmpty
            ? preferred.first.localeId
            : locales.first.localeId;
      }
    }
    if (mounted) setState(() {});
  }

  void _onSpeechStatus(String status) {
    debugPrint('STT Status: $status');
    if (!mounted) return;
    // While user still has mic "on", plugin may flip notListening between
    // segments — don't tear down UI until session ends or user stops.
    if ((status == 'notListening' || status == 'done') && !_micSessionOpen) {
      setState(() {
        _isListening = false;
        _pulseController?.stop();
        _pulseController?.reset();
        if (_lastRecognizedWords.trim().isNotEmpty) {
          _textController.text = _lastRecognizedWords.trim();
          _textController.selection = TextSelection.fromPosition(
            TextPosition(offset: _textController.text.length),
          );
        }
      });
    }
  }

  void _onSpeechError(dynamic error) {
    debugPrint('STT Error: $error');
    if (!mounted) return;

    final String errorMsg = error?.errorMsg?.toString() ?? error.toString();
    final transient =
        errorMsg.contains('error_no_match') ||
        errorMsg.contains('error_speech_timeout');
    final softRecover = transient || errorMsg.contains('error_client');

    // These often end the current listen() Future; the session loop starts
    // another pass — do not turn off the mic until the user taps stop.
    if (softRecover && _micSessionOpen) {
      return;
    }

    _micSessionOpen = false;
    setState(() {
      _isListening = false;
    });
    _pulseController?.stop();
    _pulseController?.reset();

    if (!transient) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Voice input error: $errorMsg. Try speaking clearly.'),
        ),
      );
    }
  }

  Future<void> _runSpeechListen() async {
    if (!_speechAvailable || !_micSessionOpen) return;
    await _speech.listen(
      listenFor: const Duration(seconds: 60),
      pauseFor: const Duration(seconds: 30),
      localeId: _localeId,
      partialResults: true,
      cancelOnError: false,
      listenMode: stt.ListenMode.dictation,
      onResult: (val) => setState(() {
        final words = val.recognizedWords.trim();
        if (words.isNotEmpty) {
          _lastRecognizedWords = words;
          _textController.text = words;
          _textController.selection = TextSelection.fromPosition(
            TextPosition(offset: _textController.text.length),
          );
        }
      }),
    );
  }

  Future<void> _startListening() async {
    if (!_speechAvailable) {
      _speechAvailable = await _speech.initialize(
        onStatus: _onSpeechStatus,
        onError: _onSpeechError,
      );
      if (_speechAvailable && _localeId == null) {
        final locales = await _speech.locales();
        if (locales.isNotEmpty) {
          _localeId = locales.first.localeId;
        }
      }
    }
    if (!_speechAvailable) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Speech recognition is not available on this device.'),
        ),
      );
      return;
    }

    _micSessionOpen = true;

    setState(() {
      _isListening = true;
    });
    _pulseController?.repeat(reverse: true);

    // Stay in listen until the user taps the mic again (_micSessionOpen false).
    // Do not cap passes: on emulators each listen() can return almost instantly,
    // so a low cap ended the session after only a few seconds.
    while (mounted && _micSessionOpen) {
      await _runSpeechListen();
      if (!mounted || !_micSessionOpen) break;
      await Future.delayed(const Duration(milliseconds: 400));
    }
  }

  Future<void> _stopListeningAndMaybeSend() async {
    if (!_isListening && !_micSessionOpen) return;
    _micSessionOpen = false;
    setState(() => _isListening = false);
    _pulseController?.stop();
    _pulseController?.reset();
    await _speech.stop();

    // Allow final STT result callback to update text before auto-send.
    await Future.delayed(const Duration(milliseconds: 650));
    if (!mounted) return;
    if (_textController.text.trim().isNotEmpty) {
      _sendMessage();
      return;
    }
    if (_lastRecognizedWords.trim().isNotEmpty) {
      _textController.text = _lastRecognizedWords.trim();
      _textController.selection = TextSelection.fromPosition(
        TextPosition(offset: _textController.text.length),
      );
      _sendMessage();
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text(
          'No speech captured. Check emulator mic routing or try a real device.',
        ),
      ),
    );
  }

  void _listen() async {
    if (!_isListening) {
      final permission = await Permission.microphone.request();
      if (!permission.isGranted) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Microphone permission is required for voice input.'),
          ),
        );
        return;
      }
      _lastRecognizedWords = '';
      await _startListening();
    } else {
      await _stopListeningAndMaybeSend();
    }
  }

  void _sendMessage() {
    if (_textController.text.trim().isEmpty) return;

    final text = _textController.text;
    _textController.clear();

    context.read<ChatProvider>().sendMessage(text);
  }

  @override
  Widget build(BuildContext context) {
    return SpeakardoScaffold(
      safeArea: false,
      child: SafeArea(
        top: true,
        left: true,
        right: true,
        bottom: false,
        child: Column(
          children: [
            SpeakardoTopBar(
              title: 'Speakardo',
              subtitle: _isListening ? 'Listening' : 'Active',
              trailing: IconButton.filledTonal(
                onPressed: () {},
                tooltip: 'Menu',
                icon: const Icon(Icons.menu_rounded),
                style: IconButton.styleFrom(
                  backgroundColor: Colors.white.withValues(alpha: 0.7),
                  foregroundColor: AppChrome.muted,
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
              child: GlassPanel(
                borderRadius: 20,
                padding: const EdgeInsets.symmetric(
                  horizontal: 14,
                  vertical: 10,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.calendar_today_rounded,
                      size: 16,
                      color: AppChrome.accent,
                    ),
                    const SizedBox(width: 8),
                    Text(
                      '${_weekdayLabel(DateTime.now())} • Focus Mode',
                      style: const TextStyle(
                        color: AppChrome.muted,
                        fontSize: 13,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            Expanded(
              child: Consumer<ChatProvider>(
                builder: (context, chatProvider, child) {
                  if (chatProvider.messages.isEmpty) {
                    return const _ChatEmptyState();
                  }
                  return ListView.builder(
                    reverse: true,
                    padding: const EdgeInsets.fromLTRB(4, 8, 4, 12),
                    itemCount: chatProvider.messages.length,
                    itemBuilder: (context, index) {
                      final msg = chatProvider.messages[index];
                      return MessageBubble(message: msg);
                    },
                  );
                },
              ),
            ),
            Consumer<ChatProvider>(
              builder: (context, chatProvider, child) {
                if (chatProvider.isLoading) {
                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 22),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(99),
                      child: const LinearProgressIndicator(minHeight: 3),
                    ),
                  );
                }
                return const SizedBox.shrink();
              },
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 88),
              child: Column(
                children: [
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: const [
                        _QuickActionChip(
                          icon: Icons.add_circle_outline_rounded,
                          label: 'New Reminder',
                        ),
                        _QuickActionChip(
                          icon: Icons.calendar_month_outlined,
                          label: 'View Timeline',
                        ),
                        _QuickActionChip(
                          icon: Icons.psychology_alt_outlined,
                          label: 'Memory Core',
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 10),
                  GlassPanel(
                    borderRadius: 30,
                    padding: const EdgeInsets.all(8),
                    child: Row(
                      children: [
                        IconButton(
                          onPressed: () {},
                          tooltip: 'Attach',
                          icon: const Icon(Icons.attach_file_rounded),
                          color: AppChrome.muted,
                        ),
                        Expanded(
                          child: TextField(
                            controller: _textController,
                            decoration: const InputDecoration(
                              hintText: 'Speak or type to Speakardo...',
                              border: InputBorder.none,
                              contentPadding: EdgeInsets.symmetric(
                                horizontal: 4,
                                vertical: 12,
                              ),
                            ),
                            textInputAction: TextInputAction.send,
                            onSubmitted: (_) => _sendMessage(),
                          ),
                        ),
                        AnimatedBuilder(
                          animation:
                              _pulseAnimation ??
                              const AlwaysStoppedAnimation<double>(1.0),
                          builder: (context, child) {
                            final scale = _isListening
                                ? (_pulseAnimation?.value ?? 1.0)
                                : 1.0;
                            return Transform.scale(scale: scale, child: child);
                          },
                          child: IconButton.filled(
                            onPressed: _listen,
                            tooltip: _isListening ? 'Stop listening' : 'Speak',
                            icon: Icon(
                              _isListening
                                  ? Icons.stop_rounded
                                  : Icons.mic_rounded,
                            ),
                            style: IconButton.styleFrom(
                              backgroundColor: _isListening
                                  ? Colors.redAccent
                                  : AppChrome.primary,
                              foregroundColor: Colors.white,
                              fixedSize: const Size(50, 50),
                            ),
                          ),
                        ),
                        const SizedBox(width: 4),
                        IconButton.filledTonal(
                          onPressed: _sendMessage,
                          tooltip: 'Send',
                          icon: const Icon(Icons.send_rounded),
                          style: IconButton.styleFrom(
                            backgroundColor: AppChrome.primary.withValues(
                              alpha: 0.1,
                            ),
                            foregroundColor: AppChrome.primary,
                            fixedSize: const Size(46, 46),
                          ),
                        ),
                      ],
                    ),
                  ),
                  if (_isListening)
                    const Padding(
                      padding: EdgeInsets.only(top: 8),
                      child: Text(
                        'Listening...',
                        style: TextStyle(
                          fontSize: 12,
                          color: Colors.redAccent,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _weekdayLabel(DateTime date) {
    const names = [
      'Monday',
      'Tuesday',
      'Wednesday',
      'Thursday',
      'Friday',
      'Saturday',
      'Sunday',
    ];
    return names[date.weekday - 1];
  }
}

class _QuickActionChip extends StatelessWidget {
  const _QuickActionChip({required this.icon, required this.label});

  final IconData icon;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: GlassPanel(
        borderRadius: 22,
        padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 9),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 18, color: AppChrome.primary),
            const SizedBox(width: 7),
            Text(
              label,
              style: const TextStyle(
                color: AppChrome.ink,
                fontSize: 13,
                fontWeight: FontWeight.w800,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ChatEmptyState extends StatelessWidget {
  const _ChatEmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(28),
        child: GlassPanel(
          borderRadius: 28,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: const [
              AppLogoMark(size: 54),
              SizedBox(height: 16),
              Text(
                'Good morning',
                style: TextStyle(
                  color: AppChrome.ink,
                  fontSize: 22,
                  fontWeight: FontWeight.w900,
                ),
              ),
              SizedBox(height: 8),
              Text(
                'Tell me what you need to remember. I can turn natural language into reminders.',
                textAlign: TextAlign.center,
                style: TextStyle(color: AppChrome.muted, height: 1.4),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
