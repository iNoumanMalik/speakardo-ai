import 'package:flutter/material.dart';
import 'screens/chat_screen.dart';

void main() {
  runApp(const AiReminderApp());
}

class AiReminderApp extends StatelessWidget {
  const AiReminderApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AI Reminder App',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        primarySwatch: Colors.deepPurple,
        primaryColor: const Color(0xFF6750A4),
        scaffoldBackgroundColor: Colors.white,
        appBarTheme: const AppBarTheme(
          backgroundColor: Colors.white,
          foregroundColor: Colors.black87,
          elevation: 1,
        ),
        useMaterial3: true,
      ),
      home: const ChatScreen(),
    );
  }
}
