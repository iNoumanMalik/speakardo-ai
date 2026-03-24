import 'dart:async';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:provider/provider.dart';
import 'screens/main_screen.dart';
import 'services/chat_provider.dart';
import 'services/firebase_messaging_service.dart';
import 'services/reminder_provider.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Web requires FirebaseOptions (e.g. flutterfire configure → firebase_options.dart).
  // Android/iOS use google-services / GoogleService-Info without that file.
  if (!kIsWeb) {
    await Firebase.initializeApp();
  }

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (context) => ChatProvider()),
        ChangeNotifierProvider(create: (context) => ReminderProvider()),
      ],
      child: const AiReminderApp(),
    ),
  );

  // FCM + backend registration can block for a long time (no server, slow
  // emulator, getToken). Never hold the splash screen for it.
  if (!kIsWeb) {
    unawaited(FirebaseMessagingService.initializeAndRegisterToken());
  }
}

class AiReminderApp extends StatelessWidget {
  const AiReminderApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AI Reminder App',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF6750A4)),
        useMaterial3: true,
      ),
      home: const MainScreen(),
    );
  }
}

