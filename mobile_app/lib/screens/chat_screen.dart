import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:permission_handler/permission_handler.dart';
import '../services/chat_provider.dart';
import '../widgets/message_bubble.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({Key? key}) : super(key: key);

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _textController = TextEditingController();
  final stt.SpeechToText _speech = stt.SpeechToText();
  bool _isListening = false;
  String _sttStatusText = '';
  int _noMatchRetries = 0;
  static const int _maxNoMatchRetries = 2;

  @override
  void initState() {
    super.initState();
    _initSpeech();
  }

  void _initSpeech() async {
    await Permission.microphone.request();
    await _speech.initialize(
      onStatus: _onSpeechStatus,
      onError: _onSpeechError,
    );
    if (mounted) setState(() {});
  }

  void _onSpeechStatus(String status) {
    debugPrint('STT Status: $status');
    if (!mounted) return;
    setState(() {
      _sttStatusText = status;
      if (status == 'notListening' || status == 'done') {
        _isListening = false;
      }
    });
  }

  void _onSpeechError(stt.SpeechRecognitionError error) {
    debugPrint('STT Error: $error');
    if (!mounted) return;

    // Emulator frequently returns no_match quickly; retry briefly.
    if (error.errorMsg == 'error_no_match' && _noMatchRetries < _maxNoMatchRetries) {
      _noMatchRetries += 1;
      _startListening();
      return;
    }

    setState(() {
      _isListening = false;
      _sttStatusText = error.errorMsg;
    });

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Voice input error: ${error.errorMsg}. Try speaking clearly.'),
      ),
    );
  }

  Future<void> _startListening() async {
    final available = await _speech.initialize(
      onStatus: _onSpeechStatus,
      onError: _onSpeechError,
    );
    if (!available) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Speech recognition is not available on this device.'),
        ),
      );
      return;
    }

    setState(() {
      _isListening = true;
      _sttStatusText = 'listening';
    });

    await _speech.listen(
      listenFor: const Duration(seconds: 12),
      pauseFor: const Duration(seconds: 3),
      partialResults: true,
      cancelOnError: true,
      onResult: (val) => setState(() {
        _textController.text = val.recognizedWords;
      }),
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
      _noMatchRetries = 0;
      await _startListening();
    } else {
      setState(() => _isListening = false);
      _speech.stop();
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
            if (_sttStatusText.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text(
                  _isListening ? 'Listening...' : 'Voice: $_sttStatusText',
                  style: TextStyle(
                    fontSize: 12,
                    color: _isListening ? Colors.red : Colors.grey[600],
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
                  IconButton(
                    icon: Icon(_isListening ? Icons.mic : Icons.mic_none),
                    color: _isListening ? Colors.red : const Color(0xFF6750A4),
                    onPressed: _listen,
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


