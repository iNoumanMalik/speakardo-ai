import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';

import 'device_service.dart';
import 'reminder_notification_service.dart';

/// FCM background message handler (must be top-level).
@pragma('vm:entry-point')
Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();
  await ReminderNotificationService.ensureInitialized();
  await ReminderNotificationService.handleRemoteMessage(message);
}

class FirebaseMessagingService {
  static final DeviceService _deviceService = DeviceService();
  static bool _listenersAttached = false;

  static Future<void> initializeAndRegisterToken() async {
    final messaging = FirebaseMessaging.instance;
    if (!_listenersAttached) {
      _listenersAttached = true;
      await ReminderNotificationService.ensureInitialized();

      await messaging.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        provisional: false,
      );

      FirebaseMessaging.onMessage.listen((RemoteMessage message) async {
        debugPrint('Foreground FCM: ${message.data}');
        await ReminderNotificationService.handleRemoteMessage(message);
      });

      FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) async {
        final reminderId = message.data['reminder_id']?.toString();
        if (reminderId != null) {
          await ReminderNotificationService.showReminderNotification(
            reminderId: reminderId,
            title: message.notification?.title ?? 'Reminder',
            body: message.data['task']?.toString() ??
                message.notification?.body ??
                'You have a reminder',
          );
        }
      });
    }

    final token = await messaging.getToken().timeout(
      const Duration(seconds: 20),
      onTimeout: () {
        debugPrint('FCM getToken timed out (emulator / Play services)');
        return null;
      },
    );
    if (token == null || token.isEmpty) {
      debugPrint('FCM token unavailable');
      return;
    }

    debugPrint('FCM TOKEN: $token');

    try {
      await _deviceService.registerDeviceToken(
        token: token,
        platform: _platformName(),
      );
    } catch (e) {
      debugPrint('Failed to register FCM token: $e');
    }
  }

  static String _platformName() {
    if (kIsWeb) {
      return 'web';
    }
    if (Platform.isAndroid) {
      return 'android';
    }
    if (Platform.isIOS) {
      return 'ios';
    }
    return 'unknown';
  }
}
