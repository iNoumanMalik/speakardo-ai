import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';

import '../config/app_config.dart';

String _googleSignInErrorMessage(GoogleSignInException e) {
  final detail = e.description?.trim();
  switch (e.code) {
    case GoogleSignInExceptionCode.canceled:
      return 'Google sign-in was cancelled.';
    case GoogleSignInExceptionCode.clientConfigurationError:
      return detail ??
          'Google sign-in is misconfigured. Check SHA-1 in Firebase and '
          'GOOGLE_WEB_CLIENT_ID, then fully restart the app.';
    case GoogleSignInExceptionCode.providerConfigurationError:
      return detail ??
          'Google Play Services or Firebase Auth is not set up correctly.';
    case GoogleSignInExceptionCode.uiUnavailable:
      return 'Google sign-in UI is unavailable. Add a Google account on the '
          'emulator (Settings → Passwords & accounts).';
    default:
      return detail ?? 'Google sign-in failed (${e.code.name}).';
  }
}

/// Signs in with Google via Firebase Auth and returns a Firebase ID token for the API.
class GoogleAuthService {
  GoogleAuthService._();

  static final GoogleSignIn _googleSignIn = GoogleSignIn.instance;
  static bool _initialized = false;

  static Future<void> _ensureInitialized() async {
    if (_initialized) return;
    await _googleSignIn.initialize(
      serverClientId:
          AppConfig.hasGoogleWebClientId ? AppConfig.googleWebClientId : null,
    );
    _initialized = true;
  }

  /// Returns Firebase ID token, or `null` if the user cancelled the picker.
  static Future<String?> signInAndGetIdToken() async {
    if (kIsWeb) {
      throw UnsupportedError('Google sign-in is not configured for web yet.');
    }
    if (defaultTargetPlatform == TargetPlatform.android &&
        !AppConfig.hasGoogleWebClientId) {
      throw StateError(
        'Set GOOGLE_WEB_CLIENT_ID in mobile_app/.env or pass '
        '--dart-define=GOOGLE_WEB_CLIENT_ID=your-id.apps.googleusercontent.com',
      );
    }

    await _ensureInitialized();

    final GoogleSignInAccount googleUser;
    try {
      googleUser = await _googleSignIn.authenticate();
    } on GoogleSignInException catch (e) {
      debugPrint('GoogleSignInException: $e');
      if (e.code == GoogleSignInExceptionCode.canceled) {
        return null;
      }
      throw StateError(_googleSignInErrorMessage(e));
    }
    final googleAuth = googleUser.authentication;
    final idToken = googleAuth.idToken;
    if (idToken == null || idToken.isEmpty) {
      throw StateError(
        'Google did not return an ID token. '
        'Check SHA-1 in Firebase and GOOGLE_WEB_CLIENT_ID on Android.',
      );
    }

    final credential = GoogleAuthProvider.credential(idToken: idToken);
    final UserCredential userCredential;
    try {
      userCredential =
          await FirebaseAuth.instance.signInWithCredential(credential);
    } on FirebaseAuthException catch (e) {
      debugPrint('FirebaseAuthException: ${e.code} ${e.message}');
      throw StateError(
        e.message ??
            'Firebase rejected Google sign-in (${e.code}). '
            'Enable Google in Firebase Authentication.',
      );
    }
    final firebaseIdToken = await userCredential.user?.getIdToken(true);
    if (firebaseIdToken == null || firebaseIdToken.isEmpty) {
      throw StateError('Firebase did not return an ID token.');
    }
    return firebaseIdToken;
  }

  static Future<void> signOut() async {
    await Future.wait([
      FirebaseAuth.instance.signOut(),
      _googleSignIn.signOut(),
    ]);
  }
}
