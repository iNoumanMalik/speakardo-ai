import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/models/memory_action.dart';
import 'package:mobile_app/services/api_service.dart';
import 'package:mobile_app/services/chat_provider.dart';
import 'package:mobile_app/widgets/message_bubble.dart';
import 'package:provider/provider.dart';

const _saved = {
  'type': 'saved',
  'memory_id': 'm1',
  'label': 'Saved: Your office is in Blue Area',
  'undo': true,
};

class FakeApiService extends ApiService {
  FakeApiService({this.failUndo = false});

  final bool failUndo;
  final List<String> undone = [];

  @override
  Future<Map<String, dynamic>> sendMessage(
    String message, {
    Map<String, dynamic>? pendingContext,
  }) async =>
      {
        'reply': "Got it, I'll remember that your office is in Blue Area.",
        'parsed_reminder': null,
        'intent': 'memory_save',
        'memory_actions': [_saved],
      };

  @override
  Future<void> undoMemory(String memoryId) async {
    if (failUndo) throw Exception('offline');
    undone.add(memoryId);
  }
}

void main() {
  test('MemoryAction parses the chat response', () {
    final action = MemoryAction.fromJson(_saved);
    expect(action.type, 'saved');
    expect(action.memoryId, 'm1');
    expect(action.canUndo, isTrue);
    expect(action.markUndone().canUndo, isFalse);

    final notSaved = MemoryAction.fromJson({
      'type': 'not_saved',
      'memory_id': null,
      'label': 'Not saved: sensitive',
      'undo': false,
    });
    expect(notSaved.canUndo, isFalse);
  });

  test('replies carry memory chips, and undo marks them undone', () async {
    final api = FakeApiService();
    final chat = ChatProvider(apiService: api);

    await chat.sendMessage('Remember that my office is in Blue Area');
    final reply = chat.messages.first;
    expect(reply.memoryActions.single.label, 'Saved: Your office is in Blue Area');

    final ok = await chat.undoMemoryAction(reply, reply.memoryActions.single);

    expect(ok, isTrue);
    expect(api.undone, ['m1']);
    expect(chat.messages.first.memoryActions.single.undone, isTrue);
  });

  test('a failed undo leaves the chip as it was', () async {
    final chat = ChatProvider(apiService: FakeApiService(failUndo: true));
    await chat.sendMessage('Remember that my office is in Blue Area');
    final reply = chat.messages.first;

    expect(await chat.undoMemoryAction(reply, reply.memoryActions.single), isFalse);
    expect(chat.messages.first.memoryActions.single.canUndo, isTrue);
  });

  testWidgets('tapping Undo on a chip undoes the save', (tester) async {
    final api = FakeApiService();
    final chat = ChatProvider(apiService: api);
    await chat.sendMessage('Remember that my office is in Blue Area');

    await tester.pumpWidget(
      ChangeNotifierProvider.value(
        value: chat,
        child: MaterialApp(
          home: Scaffold(
            body: Consumer<ChatProvider>(
              builder: (_, provider, _) =>
                  MessageBubble(message: provider.messages.first),
            ),
          ),
        ),
      ),
    );

    expect(find.text('Saved: Your office is in Blue Area'), findsOneWidget);
    await tester.tap(find.text('Undo'));
    await tester.pumpAndSettle();

    expect(api.undone, ['m1']);
    expect(find.text('Undo'), findsNothing);
    expect(find.text('Undone'), findsOneWidget);
  });
}
