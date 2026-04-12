import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthStorage {
  AuthStorage._();

  static const _accessKey = 'access_token';
  static const _refreshKey = 'refresh_token';

  static final FlutterSecureStorage _storage = FlutterSecureStorage(
    aOptions: const AndroidOptions(encryptedSharedPreferences: true),
  );

  static Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _storage.write(key: _accessKey, value: accessToken);
    await _storage.write(key: _refreshKey, value: refreshToken);
  }

  static Future<String?> readAccessToken() => _storage.read(key: _accessKey);

  static Future<String?> readRefreshToken() => _storage.read(key: _refreshKey);

  static Future<void> clear() async {
    await _storage.delete(key: _accessKey);
    await _storage.delete(key: _refreshKey);
  }
}
