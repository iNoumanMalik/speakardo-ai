import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:mobile_app/models/message.dart';
import 'package:mobile_app/services/api_service.dart';
import 'package:mobile_app/services/chat_provider.dart';

Map<String, dynamic> _row(String id, String role, String content, int minute) => {
      'id': id,
      'role': role,
      'content': content,
      'intent': null,
      'created_at': DateTime.utc(2026, 9, 26, 9, minute).toIso8601String(),
    };

Map<String, dynamic> _page(
  List<Map<String, dynamic>> rows, {
  bool hasMore = false,
}) =>
    {
      'messages': rows,
      'has_more': hasMore,
      'next_before': hasMore ? rows.last['id'] : null,
    };

class FakeApiService extends ApiService {
  FakeApiService(this.pages);

  final List<Map<String, dynamic>> pages;
  final List<String?> requestedBefore = [];
  Completer<void>? gate;
  Object? error;

  @override
  Future<Map<String, dynamic>> getChatHistory({
    String? before,
    int limit = 50,
  }) async {
    requestedBefore.add(before);
    if (gate != null) await gate!.future;
    if (error != null) throw error!;
    return pages.removeAt(0);
  }

  @override
  Future<Map<String, dynamic>> sendMessage(
    String message, {
    Map<String, dynamic>? pendingContext,
  }) async =>
      {'reply': 'ok', 'parsed_reminder': null};
}

void main() {
  test('loadHistory restores messages newest first, without drafts', () async {
    final api = FakeApiService([
      _page([
        _row('m2', 'assistant', 'Should I remind you?', 2),
        _row('m1', 'user', 'remind me to call mom', 1),
      ]),
    ]);
    final chat = ChatProvider(apiService: api);

    await chat.loadHistory();

    expect(chat.messages.map((m) => m.text), [
      'Should I remind you?',
      'remind me to call mom',
    ]);
    expect(chat.messages.map((m) => m.isUser), [false, true]);
    expect(chat.messages.every((m) => m.pendingReminder == null), isTrue);
    expect(chat.isHistoryLoading, isFalse);
    expect(chat.hasMoreHistory, isFalse);
  });

  test('messages sent while history loads stay in front', () async {
    final api = FakeApiService([
      _page([_row('m1', 'user', 'older', 1)]),
    ]);
    final chat = ChatProvider(apiService: api);
    chat.addMessage(
      Message(text: 'just typed', isUser: true, timestamp: DateTime.now()),
    );

    await chat.loadHistory();

    expect(chat.messages.map((m) => m.text), ['just typed', 'older']);
  });

  test('loadOlder appends the next page and stops at the end', () async {
    final api = FakeApiService([
      _page([_row('m3', 'user', 'newest', 3), _row('m2', 'user', 'middle', 2)],
          hasMore: true),
      _page([_row('m1', 'user', 'oldest', 1)]),
    ]);
    final chat = ChatProvider(apiService: api);

    await chat.loadHistory();
    await chat.loadOlder();
    await chat.loadOlder(); // no more pages: no request

    expect(chat.messages.map((m) => m.text), ['newest', 'middle', 'oldest']);
    expect(api.requestedBefore, [null, 'm2']);
    expect(chat.hasMoreHistory, isFalse);
  });

  test('overlapping loadOlder calls fetch once', () async {
    final api = FakeApiService([
      _page([_row('m2', 'user', 'b', 2)], hasMore: true),
      _page([_row('m1', 'user', 'a', 1)]),
    ]);
    final chat = ChatProvider(apiService: api);
    await chat.loadHistory();

    api.gate = Completer<void>();
    final first = chat.loadOlder();
    final second = chat.loadOlder();
    api.gate!.complete();
    await Future.wait([first, second]);

    expect(api.requestedBefore, [null, 'm2']);
    expect(chat.messages.map((m) => m.text), ['b', 'a']);
  });

  test('a page already shown is not duplicated', () async {
    final api = FakeApiService([
      _page([_row('m2', 'user', 'b', 2)], hasMore: true),
      _page([_row('m2', 'user', 'b', 2), _row('m1', 'user', 'a', 1)]),
    ]);
    final chat = ChatProvider(apiService: api);

    await chat.loadHistory();
    await chat.loadOlder();

    expect(chat.messages.map((m) => m.id), ['m2', 'm1']);
  });

  test('clear empties the chat and drops a load that finishes afterwards',
      () async {
    final api = FakeApiService([
      _page([_row('m1', 'user', "previous user's message", 1)]),
    ]);
    final chat = ChatProvider(apiService: api);
    api.gate = Completer<void>();

    final loading = chat.loadHistory();
    chat.clear();
    api.gate!.complete();
    await loading;

    expect(chat.messages, isEmpty);
    expect(chat.isHistoryLoading, isFalse);
  });

  test('a failed history load leaves chat usable', () async {
    final api = FakeApiService([])..error = Exception('offline');
    final chat = ChatProvider(apiService: api);

    await chat.loadHistory();
    await chat.sendMessage('hello');

    expect(chat.isHistoryLoading, isFalse);
    expect(chat.messages.map((m) => m.text), ['ok', 'hello']);
  });
}
