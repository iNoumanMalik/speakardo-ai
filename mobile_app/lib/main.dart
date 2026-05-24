import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:provider/provider.dart';
import 'services/notification_background.dart';
import 'services/reminder_notification_service.dart';
import 'package:timezone/data/latest_all.dart';
import 'screens/login_screen.dart';
import 'screens/main_screen.dart';
import 'screens/onboarding_screen.dart';
import 'config/app_config.dart';
import 'services/auth_provider.dart';
import 'services/chat_provider.dart';
import 'services/onboarding_storage.dart';
import 'services/profile_provider.dart';
import 'services/reminder_provider.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await AppConfig.initialize();
  initializeTimeZones();
  // Web requires FirebaseOptions (e.g. flutterfire configure → firebase_options.dart).
  // Android/iOS use google-services / GoogleService-Info without that file.
  if (!kIsWeb) {
    await Firebase.initializeApp();
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
    await ReminderNotificationService.ensureInitialized();
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

class _AuthGate extends StatefulWidget {
  const _AuthGate();

  @override
  State<_AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<_AuthGate> {
  bool? _onboardingComplete;

  @override
  void initState() {
    super.initState();
    OnboardingStorage.isComplete().then((done) {
      if (mounted) {
        setState(() => _onboardingComplete = done);
      }
    });
  }

  void _onOnboardingFinished() {
    setState(() => _onboardingComplete = true);
  }

  @override
  Widget build(BuildContext context) {
    return Consumer<AuthProvider>(
      builder: (context, auth, _) {
        if (!auth.isReady || _onboardingComplete == null) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }

        if (!auth.isLoggedIn && _onboardingComplete == false) {
          return OnboardingScreen(onFinished: _onOnboardingFinished);
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
  const AiReminderApp({super.key});

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
