import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:mobile_app/main.dart';
import 'package:mobile_app/services/auth_provider.dart';
import 'package:mobile_app/services/chat_provider.dart';
import 'package:mobile_app/services/profile_provider.dart';
import 'package:mobile_app/services/reminder_provider.dart';

void main() {
  testWidgets('App shows auth bootstrap loading', (WidgetTester tester) async {
    await tester.pumpWidget(
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

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });
}
