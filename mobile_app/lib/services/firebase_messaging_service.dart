import 'dart:io';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import 'device_service.dart';

class FirebaseMessagingService {
  static final DeviceService _deviceService = DeviceService();
  static bool _bootstrapped = false;
  static const String _channelId = 'high_importance_channel';
  static const String _channelName = 'High Importance Notifications';
  static const String _channelDescription = 'Reminder alerts';
  static final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();

  static Future<void> _setupLocalNotifications() async {
    const androidChannel = AndroidNotificationChannel(
      _channelId,
      _channelName,
      description: _channelDescription,
      importance: Importance.max,
    );

    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const settings = InitializationSettings(android: androidSettings);
    await _localNotifications.initialize(settings);

    await _localNotifications
        .resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
        ?.createNotificationChannel(androidChannel);
  }

  static Future<void> _showForegroundNotification(RemoteMessage message) async {
    final notification = message.notification;
    final title = notification?.title ?? 'Reminder';
    final body = notification?.body ?? 'You have a pending reminder';

    const androidDetails = AndroidNotificationDetails(
      _channelId,
      _channelName,
      channelDescription: _channelDescription,
      importance: Importance.max,
      priority: Priority.high,
      playSound: true,
    );

    await _localNotifications.show(
      message.hashCode,
      title,
      body,
      const NotificationDetails(android: androidDetails),
    );
  }

  static Future<void> initializeAndRegisterToken() async {
    if (_bootstrapped) {
      return;
    }
    _bootstrapped = true;

    final messaging = FirebaseMessaging.instance;
    await _setupLocalNotifications();

    await messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
      provisional: false,
    );

    FirebaseMessaging.onMessage.listen((RemoteMessage message) async {
      debugPrint('Foreground notification: ${message.notification?.title}');
      await _showForegroundNotification(message);
    });

    final token = await messaging.getToken();
    if (token == null || token.isEmpty) {
      debugPrint('FCM token unavailable');
      return;
    }

    debugPrint('FCM TOKEN: $token');

    try {
      await _deviceService.registerDeviceToken(
        token: token,
        userId: null,
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
