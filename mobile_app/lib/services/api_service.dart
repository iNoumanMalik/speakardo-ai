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

  Future<void> patchReminder(String id, Map<String, dynamic> reminderData) async {
    final response = await AuthHttp.patchJson(
      Uri.parse('$baseUrl/reminders/$id'),
      reminderData,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to update reminder: ${response.statusCode}');
    }
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

  Future<void> deleteReminder(String id) async {
    final response = await AuthHttp.delete(Uri.parse('$baseUrl/reminders/$id'));

    if (response.statusCode != 200) {
      throw Exception('Failed to delete reminder');
    }
  }
}
