import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:permission_handler/permission_handler.dart';
import 'dart:ui' as ui;
import '../services/chat_provider.dart';
import '../widgets/message_bubble.dart';

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
        final deviceLanguage = ui.PlatformDispatcher.instance.locale.languageCode;
        final preferred = locales.where(
          (l) => l.localeId.toLowerCase().startsWith(deviceLanguage.toLowerCase()),
        );
        _localeId = preferred.isNotEmpty ? preferred.first.localeId : locales.first.localeId;
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
    final softRecover =
        transient || errorMsg.contains('error_client');

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
    return Scaffold(
      appBar: AppBar(
        title: const Text('Ethereal AI Reminder'),
        elevation: 1,
        // Voice feedback toggle (speaker icon) — TTS disabled.
        // actions: [
        //   Consumer<ChatProvider>(
        //     builder: (context, chatProvider, _) {
        //       return IconButton(
        //         tooltip: chatProvider.voiceFeedbackEnabled
        //             ? 'Voice feedback on'
        //             : 'Voice feedback off',
        //         icon: Icon(
        //           chatProvider.voiceFeedbackEnabled
        //               ? Icons.volume_up
        //               : Icons.volume_off,
        //         ),
        //         onPressed: () {
        //           chatProvider.setVoiceFeedbackEnabled(
        //             !chatProvider.voiceFeedbackEnabled,
        //           );
        //         },
        //       );
        //     },
        //   ),
        // ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: Consumer<ChatProvider>(
                builder: (context, chatProvider, child) {
                  return ListView.builder(
                    reverse: true,
                    itemCount: chatProvider.messages.length,
                    itemBuilder: (context, index) {
                      final msg = chatProvider.messages[index];
                      return MessageBubble(
                        message: msg,
                      );
                    },
                  );
                },
              ),
            ),
            Consumer<ChatProvider>(
              builder: (context, chatProvider, child) {
                if (chatProvider.isLoading) {
                  return const Padding(
                    padding: EdgeInsets.all(8.0),
                    child: LinearProgressIndicator(),
                  );
                }
                return const SizedBox.shrink();
              },
            ),
            if (_isListening)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(
                  'Listening...',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.red,
                  ),
                ),
              ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 8.0),
              decoration: BoxDecoration(
                color: Theme.of(context).cardColor,
                boxShadow: [
                  BoxShadow(
                    offset: const Offset(0, -1),
                    blurRadius: 5,
                    color: Colors.black.withOpacity(0.05),
                  ),
                ],
              ),
              child: Row(
                children: [
                  GestureDetector(
                    onTap: _listen,
                    child: AnimatedBuilder(
                      animation: _pulseAnimation ?? const AlwaysStoppedAnimation<double>(1.0),
                      builder: (context, child) {
                        final scale = _isListening ? (_pulseAnimation?.value ?? 1.0) : 1.0;
                        return Transform.scale(scale: scale, child: child);
                      },
                      child: Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: _isListening
                              ? Colors.red.withValues(alpha: 0.15)
                              : Colors.transparent,
                          shape: BoxShape.circle,
                        ),
                        child: Icon(
                          _isListening ? Icons.mic : Icons.mic_none,
                          color: _isListening ? Colors.red : const Color(0xFF6750A4),
                        ),
                      ),
                    ),
                  ),
                  Expanded(
                    child: TextField(
                      controller: _textController,
                      decoration: InputDecoration(
                        hintText: 'Type or speak a reminder...',
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(25.0),
                          borderSide: BorderSide.none,
                        ),
                        filled: true,
                        fillColor: Colors.grey[100],
                        contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                      ),
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _sendMessage(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  GestureDetector(
                    onTap: _sendMessage,
                    child: CircleAvatar(
                      backgroundColor: const Color(0xFF6750A4),
                      child: const Icon(Icons.send, color: Colors.white),
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
}


