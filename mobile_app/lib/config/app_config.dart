import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

class AppConfig {
  static const String backendUrlAndroid = 'http://10.0.2.2:8000';
  static const String backendUrliOS = 'http://127.0.0.1:8000';
  static const String backendUrlProd = 'https://api.aireminder.app';

  static bool _initialized = false;

  /// Load env from bundled `.env` or `.env.example`.
  /// Create `mobile_app/.env` from `.env.example` with your values.
  /// Call once from `main()` before `runApp`.
  static Future<void> initialize() async {
    if (_initialized) return;
    for (final name in ['.env', '.env.example']) {
      try {
        await dotenv.load(fileName: name);
        break;
      } catch (_) {
        continue;
      }
    }
    _initialized = true;
  }

  /// Firebase Web OAuth client ID.
  /// Priority: `--dart-define=GOOGLE_WEB_CLIENT_ID=...` then `.env`.
  static String get googleWebClientId {
    const fromDartDefine = String.fromEnvironment('GOOGLE_WEB_CLIENT_ID');
    if (fromDartDefine.trim().isNotEmpty) {
      return fromDartDefine.trim();
    }
    return dotenv.env['GOOGLE_WEB_CLIENT_ID']?.trim() ?? '';
  }

  static bool get hasGoogleWebClientId =>
      googleWebClientId.isNotEmpty && !googleWebClientId.contains('YOUR_');

  static String get baseUrl {
    if (kReleaseMode) {
      return backendUrlProd;
    }
    if (Platform.isAndroid) {
      return backendUrlAndroid;
    } else if (Platform.isIOS) {
      return backendUrliOS;
    }
    return backendUrliOS;
  }
}
