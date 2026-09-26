import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/app_config.dart';
import 'auth_http.dart';

class ApiService {
  static final String baseUrl = AppConfig.baseUrl;

  /// Phase 2: optional [pendingContext] for clarification + edits (recent reminders come from the server).
  Future<Map<String, dynamic>> sendMessage(
    String message, {
    Map<String, dynamic>? pendingContext,
  }) async {
    final body = <String, dynamic>{'message': message};
    if (pendingContext != null && pendingContext.isNotEmpty) {
      body['pending_context'] = pendingContext;
    }

    final response = await AuthHttp.postJson(
      Uri.parse('$baseUrl/chat'),
      body,
    ).timeout(
      const Duration(seconds: 120),
      onTimeout: () => http.Response('', 408),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception('Failed to send message: ${response.statusCode}');
  }

  /// Newest-first page of stored chat messages. Pass the previous page's
  /// `next_before` as [before] to load older messages.
  Future<Map<String, dynamic>> getChatHistory({
    String? before,
    int limit = 50,
  }) async {
    final query = <String, String>{'limit': '$limit'};
    if (before != null) query['before'] = before;
    final response = await AuthHttp.get(
      Uri.parse('$baseUrl/chat/history').replace(queryParameters: query),
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception(_errorBody(response, 'Failed to load chat history'));
  }

  Future<Map<String, dynamic>> patchReminder(
    String id,
    Map<String, dynamic> reminderData,
  ) async {
    final response = await AuthHttp.patchJson(
      Uri.parse('$baseUrl/reminders/$id'),
      reminderData,
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception(_errorBody(response, 'Failed to update reminder'));
  }

  Future<Map<String, dynamic>> republishReminder(
    String id, {
    String? task,
    String? datetimeUtcIso,
    String? repeat,
  }) async {
    final body = <String, dynamic>{};
    if (task != null) body['task'] = task;
    if (datetimeUtcIso != null) body['datetime'] = datetimeUtcIso;
    if (repeat != null) body['repeat'] = repeat;
    final response = await AuthHttp.postJson(
      Uri.parse('$baseUrl/reminders/$id/republish'),
      body,
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception(_errorBody(response, 'Failed to republish reminder'));
  }

  static String _errorBody(http.Response response, String fallback) {
    try {
      final map = jsonDecode(response.body);
      if (map is Map && map['detail'] != null) {
        return map['detail'].toString();
      }
    } catch (_) {}
    return '$fallback (${response.statusCode})';
  }

  Future<void> createReminder(Map<String, dynamic> reminderData) async {
    final response = await AuthHttp.postJson(
      Uri.parse('$baseUrl/reminders'),
      reminderData,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to create reminder: ${response.statusCode}');
    }
  }

  Future<List<dynamic>> getReminders() async {
    final response = await AuthHttp.get(Uri.parse('$baseUrl/reminders'));

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as List<dynamic>;
    }
    throw Exception('Failed to load reminders');
  }

  Future<void> completeReminder(String id) async {
    final response = await AuthHttp.patch(
      Uri.parse('$baseUrl/reminders/$id/complete'),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to update reminder');
    }
  }

  Future<void> snoozeReminder(String id, int minutes) async {
    final response = await AuthHttp.postJson(
      Uri.parse('$baseUrl/reminders/$id/snooze'),
      {'minutes': minutes},
    );

    if (response.statusCode != 200) {
      throw Exception(
        'Failed to snooze reminder (${response.statusCode}): ${response.body}',
      );
    }
  }

  Future<void> deleteReminder(String id) async {
    final response = await AuthHttp.delete(Uri.parse('$baseUrl/reminders/$id'));

    if (response.statusCode != 200) {
      throw Exception('Failed to delete reminder');
    }
  }
}
