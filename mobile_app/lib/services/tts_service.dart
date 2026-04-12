import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';

class TtsService {
  static final FlutterTts _tts = FlutterTts();
  static bool _configured = false;

  static Future<void> _ensureConfigured() async {
    if (_configured) return;
    _configured = true;
    await _tts.setLanguage('en-US');
    await _tts.setSpeechRate(0.5);
    await _tts.setVolume(1.0);
    await _tts.setPitch(1.0);
  }

  static Future<void> speak(String text) async {
    final trimmed = text.trim();
    if (trimmed.isEmpty) return;
    try {
      await _ensureConfigured();
      await _tts.stop();
      await _tts.speak(trimmed);
    } catch (e) {
      debugPrint('TTS error: $e');
    }
  }
}
