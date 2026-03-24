import 'package:flutter/material.dart';
import '../models/message.dart';
import 'api_service.dart';
import 'package:intl/intl.dart';

class ChatProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  final List<Message> _messages = [];
  bool _isLoading = false;

  /// Last assistant draft for Phase 2 (clarification, time follow-up, edit-in-chat).
  Map<String, dynamic>? _pendingContext;

  List<Message> get messages => _messages;
  bool get isLoading => _isLoading;

  void addMessage(Message message) {
    _messages.insert(0, message);
    notifyListeners();
  }

  void _clearPendingReminderFor(Map<String, dynamic> reminderData) {
    final int idx = _messages.indexWhere(
      (m) =>
          !m.isUser &&
          m.pendingReminder != null &&
          identical(m.pendingReminder, reminderData),
    );
    if (idx != -1) {
      _messages[idx] = _messages[idx].copyWith(clearPendingReminder: true);
    }
  }

  Future<List<Map<String, dynamic>>> _recentRemindersPayload() async {
    try {
      final list = await _apiService.getReminders();
      final out = <Map<String, dynamic>>[];
      for (final raw in list) {
        if (raw is! Map) continue;
        final m = Map<String, dynamic>.from(raw);
        final status = m['status']?.toString();
        if (status == 'completed') continue;
        out.add({
          'id': m['id'],
          'task': m['task'],
          'datetime': m['datetime'],
        });
        if (out.length >= 20) break;
      }
      return out;
    } catch (_) {
      return [];
    }
  }

  DateTime _localDateTimeFromDraft(Map<String, dynamic> action) {
    final String date = action['date'] as String;
    final String time = action['time'] as String;
    final normalizedTime = time.length == 5 ? '$time:00' : time;
    return DateTime.parse('${date}T$normalizedTime');
  }

  Future<void> _applyClientAction(Map<String, dynamic> action) async {
    final type = action['type']?.toString();
    if (type != 'patch_reminder') return;

    final id = action['reminder_id']?.toString();
    if (id == null || id.isEmpty) return;

    final task = action['task'] as String?;
    if (task == null) return;

    final local = _localDateTimeFromDraft({
      'date': action['date'],
      'time': action['time'],
    });

    final payload = <String, dynamic>{
      'task': task,
      'datetime': local.toUtc().toIso8601String(),
    };
    final repeat = action['repeat'];
    if (repeat != null) {
      payload['repeat'] = repeat;
    }

    await _apiService.patchReminder(id, payload);
  }

  Future<void> sendMessage(String text) async {
    addMessage(Message(
      text: text,
      isUser: true,
      timestamp: DateTime.now(),
    ));

    _isLoading = true;
    notifyListeners();

    try {
      final recent = await _recentRemindersPayload();
      final response = await _apiService.sendMessage(
        text,
        pendingContext: _pendingContext,
        recentReminders: recent.isEmpty ? null : recent,
      );

      final reply = response['reply'] as String? ?? '';
      final clientAction = response['client_action'];
      final parsedReminder = response['parsed_reminder'];

      if (clientAction is Map) {
        try {
          await _applyClientAction(Map<String, dynamic>.from(clientAction));
          _pendingContext = null;
          addMessage(Message(
            text: reply,
            isUser: false,
            timestamp: DateTime.now(),
          ));
        } catch (e) {
          addMessage(Message(
            text: 'Could not update reminder: $e',
            isUser: false,
            timestamp: DateTime.now(),
          ));
        }
        return;
      }

      if (parsedReminder is Map) {
        _pendingContext = Map<String, dynamic>.from(parsedReminder);
        addMessage(Message(
          text: reply,
          isUser: false,
          timestamp: DateTime.now(),
          pendingReminder: Map<String, dynamic>.from(parsedReminder),
        ));
      } else {
        _pendingContext = null;
        addMessage(Message(
          text: reply,
          isUser: false,
          timestamp: DateTime.now(),
        ));
      }
    } catch (e) {
      addMessage(Message(
        text: 'Error: $e',
        isUser: false,
        timestamp: DateTime.now(),
      ));
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> confirmReminder(Map<String, dynamic> reminderData) async {
    if (reminderData['confirmable'] == false) {
      return;
    }

    _isLoading = true;
    notifyListeners();

    try {
      final String task = reminderData['task'] ?? 'No Task';
      final String date =
          reminderData['date'] ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
      final String time = reminderData['time'] ?? '00:00';
      final String? repeat = reminderData['repeat'] as String?;

      final normalizedTime = time.length == 5 ? '$time:00' : time;
      final DateTime local = DateTime.parse('${date}T$normalizedTime');

      await _apiService.createReminder({
        'task': task,
        'datetime': local.toUtc().toIso8601String(),
        'repeat': repeat,
      });

      _clearPendingReminderFor(reminderData);
      _pendingContext = null;

      addMessage(Message(
        text: "Reminder saved! I'll remind you to $task on $date at $time.",
        isUser: false,
        timestamp: DateTime.now(),
      ));
    } catch (e) {
      addMessage(Message(
        text: 'Failed to save reminder: $e',
        isUser: false,
        timestamp: DateTime.now(),
      ));
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  void rejectReminder(Map<String, dynamic> reminderData) {
    _clearPendingReminderFor(reminderData);
    _pendingContext = null;
    addMessage(
      Message(
        text:
            'No problem. Please tell me the reminder again with updated details '
            '(for example: \'Remind me to take medicine at 12 PM\').',
        isUser: false,
        timestamp: DateTime.now(),
      ),
    );
    notifyListeners();
  }
}
