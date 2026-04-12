import 'dart:async';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

import 'auth_http.dart';
import 'auth_service.dart';
import 'auth_storage.dart';
import 'firebase_messaging_service.dart';

class AuthProvider extends ChangeNotifier {
  AuthProvider() {
    AuthHttp.onSessionExpired = _onSessionExpired;
    unawaited(_bootstrap());
  }

  bool _ready = false;
  bool _loggedIn = false;

  bool get isReady => _ready;
  bool get isLoggedIn => _loggedIn;

  void _onSessionExpired() {
    _loggedIn = false;
    notifyListeners();
  }

  Future<void> _bootstrap() async {
    final access = await AuthStorage.readAccessToken();
    final refresh = await AuthStorage.readRefreshToken();
    if ((access == null || access.isEmpty) &&
        refresh != null &&
        refresh.isNotEmpty) {
      await AuthService.tryRefresh();
    }
    final a = await AuthStorage.readAccessToken();
    _loggedIn = a != null && a.isNotEmpty;
    _ready = true;
    notifyListeners();

    if (_loggedIn && !kIsWeb) {
      unawaited(FirebaseMessagingService.initializeAndRegisterToken());
    }
  }

  Future<String?> login(String email, String password) async {
    final err = await AuthService.login(email, password);
    if (err != null) return err;
    _loggedIn = true;
    notifyListeners();
    if (!kIsWeb) {
      unawaited(FirebaseMessagingService.initializeAndRegisterToken());
    }
    return null;
  }

  Future<String?> register(String email, String password) async {
    final err = await AuthService.register(email, password);
    if (err != null) return err;
    _loggedIn = true;
    notifyListeners();
    if (!kIsWeb) {
      unawaited(FirebaseMessagingService.initializeAndRegisterToken());
    }
    return null;
  }

  Future<void> logout() async {
    await AuthService.logout();
    _loggedIn = false;
    notifyListeners();
  }
}
