import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:provider/provider.dart';
import 'package:timezone/data/latest_all.dart';
import 'screens/login_screen.dart';
import 'screens/main_screen.dart';
import 'services/auth_provider.dart';
import 'services/chat_provider.dart';
import 'services/profile_provider.dart';
import 'services/reminder_provider.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  initializeTimeZones();
  // Web requires FirebaseOptions (e.g. flutterfire configure → firebase_options.dart).
  // Android/iOS use google-services / GoogleService-Info without that file.
  if (!kIsWeb) {
    await Firebase.initializeApp();
  }

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => ChatProvider()),
        ChangeNotifierProvider(create: (_) => ReminderProvider()),
        ChangeNotifierProvider(create: (_) => ProfileProvider()),
      ],
      child: const AiReminderApp(),
    ),
  );
}

class _AuthGate extends StatelessWidget {
  const _AuthGate();

  @override
  Widget build(BuildContext context) {
    return Consumer<AuthProvider>(
      builder: (context, auth, _) {
        if (!auth.isReady) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        if (!auth.isLoggedIn) {
          return const LoginScreen();
        }
        return const MainScreen();
      },
    );
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
      home: const _AuthGate(),
    );
  }
}

