import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart' show debugPrint, kIsWeb;
import 'package:flutter/material.dart';

import 'auth_http.dart';
import 'auth_service.dart';
import 'auth_storage.dart';
import 'firebase_messaging_service.dart';
import 'google_auth_service.dart';

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

  Future<String?> signInWithGoogle() async {
    if (kIsWeb) {
      return 'Google sign-in is not supported on web yet.';
    }
    try {
      final idToken = await GoogleAuthService.signInAndGetIdToken();
      if (idToken == null) {
        return null;
      }
      final err = await AuthService.loginWithGoogle(idToken);
      if (err != null) return err;
      _loggedIn = true;
      notifyListeners();
      unawaited(FirebaseMessagingService.initializeAndRegisterToken());
      return null;
    } on StateError catch (e) {
      return e.message;
    } on FirebaseException catch (e) {
      return e.message ?? 'Firebase error: ${e.code}';
    } catch (e, st) {
      debugPrint('signInWithGoogle error: $e\n$st');
      return 'Google sign-in failed. Please try again.';
    }
  }

  Future<void> logout() async {
    if (!kIsWeb) {
      try {
        await GoogleAuthService.signOut();
      } catch (_) {}
    }
    await AuthService.logout();
    _loggedIn = false;
    notifyListeners();
  }
}
