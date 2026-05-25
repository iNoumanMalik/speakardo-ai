import 'dart:io';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

import 'device_service.dart';
import 'notification_router.dart';
import 'reminder_notification_service.dart';

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

      FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
        NotificationRouter.handleFcmData(message.data);
      });

      final initialMessage = await messaging.getInitialMessage();
      if (initialMessage != null) {
        NotificationRouter.handleFcmData(initialMessage.data);
      }
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
