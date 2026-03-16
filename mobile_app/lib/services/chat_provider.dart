import 'package:flutter/material.dart';
import '../models/message.dart';
import 'api_service.dart';
import 'package:intl/intl.dart';

class ChatProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  final List<Message> _messages = [];
  bool _isLoading = false;

  List<Message> get messages => _messages;
  bool get isLoading => _isLoading;

  void addMessage(Message message) {
    _messages.insert(0, message);
    notifyListeners();
  }

  Future<void> sendMessage(String text) async {
    // 1. Add user message
    addMessage(Message(
      text: text,
      isUser: true,
      timestamp: DateTime.now(),
    ));

    _isLoading = true;
    notifyListeners();

    try {
      // 2. Send to backend
      final response = await _apiService.sendMessage(text);
      final reply = response['reply'];
      final parsedReminder = response['parsed_reminder'];

      // 3. Add bot response
      addMessage(Message(
        text: reply,
        isUser: false,
        timestamp: DateTime.now(),
        pendingReminder: parsedReminder,
      ));
    } catch (e) {
      addMessage(Message(
        text: "Error: $e",
        isUser: false,
        timestamp: DateTime.now(),
      ));
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> confirmReminder(Map<String, dynamic> reminderData) async {
    _isLoading = true;
    notifyListeners();

    try {
      // The backend expects specific fields. 
      // ai_service/extractor returns {task, date, time, repeat}
      // routers/reminders.py expects {task, datetime, repeat, user_id}
      
      final String task = reminderData['task'] ?? 'No Task';
      final String date = reminderData['date'] ?? DateFormat('yyyy-MM-dd').format(DateTime.now());
      final String time = reminderData['time'] ?? '00:00';
      final String? repeat = reminderData['repeat'];
      
      final DateTime datetime = DateTime.parse('${date}T${time}:00');

      await _apiService.createReminder({
        'task': task,
        'datetime': datetime.toIso8601String(),
        'repeat': repeat,
      });

      addMessage(Message(
        text: "Reminder saved! I'll remind you to $task on $date at $time.",
        isUser: false,
        timestamp: DateTime.now(),
      ));
    } catch (e) {
      addMessage(Message(
        text: "Failed to save reminder: $e",
        isUser: false,
        timestamp: DateTime.now(),
      ));
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
