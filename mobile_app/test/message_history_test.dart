import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/models/message.dart';

void main() {
  test('fromHistoryJson maps role, content, id and converts UTC to local', () {
    final user = Message.fromHistoryJson({
      'id': 'abc',
      'role': 'user',
      'content': 'remind me to call mom',
      'intent': 'create',
      'created_at': '2026-09-26T10:15:01.004000+00:00',
    });
    final assistant = Message.fromHistoryJson({
      'id': 'def',
      'role': 'assistant',
      'content': 'Should I remind you?',
      'intent': null,
      'created_at': '2026-09-26T10:15:02.120000+00:00',
    });

    expect(user.id, 'abc');
    expect(user.isUser, isTrue);
    expect(user.text, 'remind me to call mom');
    expect(user.pendingReminder, isNull);
    expect(user.timestamp, DateTime.utc(2026, 9, 26, 10, 15, 1, 4).toLocal());
    expect(user.timestamp.isUtc, isFalse);
    expect(assistant.isUser, isFalse);
  });

  test('copyWith keeps the server id', () {
    final message = Message(
      id: 'abc',
      text: 'hi',
      isUser: true,
      timestamp: DateTime(2026, 9, 26),
    );

    expect(message.copyWith(text: 'edited').id, 'abc');
  });
}
