import 'package:flutter/material.dart';

import '../services/auth_service.dart';
import '../widgets/app_chrome.dart';

class ResetPasswordScreen extends StatefulWidget {
  const ResetPasswordScreen({super.key, this.initialToken});

  final String? initialToken;

  @override
  State<ResetPasswordScreen> createState() => _ResetPasswordScreenState();
}

class _ResetPasswordScreenState extends State<ResetPasswordScreen> {
  late final TextEditingController _token;
  final _password = TextEditingController();
  final _confirm = TextEditingController();
  bool _busy = false;
  bool _done = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _token = TextEditingController(text: widget.initialToken ?? '');
  }

  @override
  void dispose() {
    _token.dispose();
    _password.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final token = _token.text.trim();
    final password = _password.text;
    final confirm = _confirm.text;
    if (token.isEmpty) {
      setState(() => _error = 'Paste the reset token from your email link.');
      return;
    }
    if (password.length < 8) {
      setState(() => _error = 'Password must be at least 8 characters.');
      return;
    }
    if (password != confirm) {
      setState(() => _error = 'Passwords do not match.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final err = await AuthService.resetPassword(token, password);
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (err != null) {
        _error = err;
      } else {
        _done = true;
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return SpeakardoScaffold(
      appBar: AppBar(
        title: const Text(
          'Reset password',
          style: TextStyle(
            color: AppChrome.ink,
            fontWeight: FontWeight.w800,
          ),
        ),
        backgroundColor: Colors.transparent,
        elevation: 0,
        iconTheme: const IconThemeData(color: AppChrome.ink),
      ),
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 400),
            child: GlassPanel(
              borderRadius: 28,
              padding: const EdgeInsets.all(28),
              child: _done
                  ? Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Icon(
                          Icons.check_circle_outline,
                          size: 64,
                          color: AppChrome.accent,
                        ),
                        const SizedBox(height: 20),
                        const Text(
                          'Password updated',
                          style: TextStyle(
                            color: AppChrome.ink,
                            fontSize: 20,
                            fontWeight: FontWeight.w900,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 12),
                        const Text(
                          'You can sign in with your new password.',
                          style: TextStyle(
                            color: AppChrome.muted,
                            fontSize: 14,
                            height: 1.4,
                          ),
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 24),
                        FilledButton(
                          onPressed: () => Navigator.popUntil(
                            context,
                            (route) => route.isFirst,
                          ),
                          style: AppChrome.primaryButtonStyle(),
                          child: const Text('Back to sign in'),
                        ),
                      ],
                    )
                  : Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Text(
                          'Choose a new password. If you opened the email on '
                          'this device, the token may already be filled in.',
                          style: TextStyle(
                            color: AppChrome.ink,
                            fontSize: 14,
                            height: 1.4,
                          ),
                        ),
                        const SizedBox(height: 20),
                        TextField(
                          controller: _token,
                          enabled: !_busy,
                          decoration: AppChrome.inputDecoration(
                            label: 'Reset token',
                            helperText: 'From the password reset email link',
                          ),
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: _password,
                          obscureText: true,
                          enabled: !_busy,
                          decoration: AppChrome.inputDecoration(
                            label: 'New password',
                            helperText: 'At least 8 characters',
                          ),
                        ),
                        const SizedBox(height: 12),
                        TextField(
                          controller: _confirm,
                          obscureText: true,
                          enabled: !_busy,
                          decoration: AppChrome.inputDecoration(
                            label: 'Confirm password',
                          ),
                        ),
                        if (_error != null) ...[
                          const SizedBox(height: 12),
                          Text(
                            _error!,
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.error,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                        const SizedBox(height: 20),
                        FilledButton(
                          onPressed: _busy ? null : _submit,
                          style: AppChrome.primaryButtonStyle(),
                          child: _busy
                              ? const SizedBox(
                                  height: 22,
                                  width: 22,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: Colors.white,
                                  ),
                                )
                              : const Text('Update password'),
                        ),
                      ],
                    ),
            ),
          ),
        ),
      ),
    );
  }
}
