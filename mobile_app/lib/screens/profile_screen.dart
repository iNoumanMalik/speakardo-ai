import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/auth_provider.dart';
import '../services/feedback_service.dart';
import '../services/profile_provider.dart';
import '../widgets/app_chrome.dart';
// Timezone UI hidden (Option A). Kept for future use:
// import '../utils/timezone_options.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final FeedbackService _feedbackService = FeedbackService();
  PackageInfo? _packageInfo;
  bool _isSubmittingFeedback = false;

  @override
  void initState() {
    super.initState();
    _loadPackageInfo();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ProfileProvider>().fetchProfile();
    });
  }

  Future<void> _loadPackageInfo() async {
    final info = await PackageInfo.fromPlatform();
    if (!mounted) return;
    setState(() => _packageInfo = info);
  }

  void _showError(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Theme.of(context).colorScheme.error,
      ),
    );
  }

  void _showSuccess(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  Future<void> _showFeedbackForm() async {
    final controller = TextEditingController();

    final submitted = await showDialog<bool>(
      context: context,
      builder: (context) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
          title: const Text(
            'Send feedback',
            style: TextStyle(color: AppChrome.ink, fontWeight: FontWeight.w900),
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Tell us what you like or what we should improve.',
                  style: TextStyle(color: AppChrome.muted, height: 1.4),
                ),
                const SizedBox(height: 16),
                TextField(
                  controller: controller,
                  maxLines: 5,
                  maxLength: 2000,
                  decoration: AppChrome.inputDecoration(
                    label: 'Feedback description',
                    hint: 'Your feedback...',
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              style: TextButton.styleFrom(
                foregroundColor: AppChrome.muted,
                textStyle: const TextStyle(fontWeight: FontWeight.w600),
              ),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () {
                if (controller.text.trim().length < 3) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Please enter at least 3 characters.'),
                    ),
                  );
                  return;
                }
                Navigator.pop(context, true);
              },
              style: AppChrome.primaryButtonStyle(),
              child: const Text('Submit'),
            ),
          ],
        );
      },
    );

    if (submitted != true || !mounted) return;

    setState(() => _isSubmittingFeedback = true);
    try {
      await _feedbackService.submitFeedback(controller.text);
      if (!mounted) return;
      _showSuccess('Thanks! Your feedback was submitted.');
    } catch (_) {
      if (!mounted) return;
      _showError('Could not submit feedback. Please try again.');
    } finally {
      controller.dispose();
      if (mounted) {
        setState(() => _isSubmittingFeedback = false);
      }
    }
  }

  // FAQ removed in favor of in-app feedback.

  Future<void> _contactSupport() async {
    final uri = Uri(
      scheme: 'mailto',
      path: 'support@aireminder.app',
      query: 'subject=AI Reminder App Support',
    );
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      _showError('Could not open email app.');
    }
  }

  // Timezone picker hidden (Option A — device local time for reminders).
  // Kept for when profile timezone is wired end-to-end.
  /*
  Future<void> _pickTimezone(ProfileProvider provider) async {
    final options = timezoneOptionsFor(provider.timezone);
    ...
  }
  */

  Widget _sectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 20, 4, 8),
      child: Text(
        title.toUpperCase(),
        style: const TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w900,
          color: AppChrome.primary,
          letterSpacing: 1.0,
        ),
      ),
    );
  }

  Widget _buildSettingsIcon() {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        color: AppChrome.primary.withValues(alpha: 0.1),
        border: Border.all(color: AppChrome.primary.withValues(alpha: 0.18)),
      ),
      child: const Icon(
        Icons.settings_suggest_rounded,
        color: AppChrome.primary,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return SpeakardoScaffold(
      child: Consumer<ProfileProvider>(
        builder: (context, provider, _) {
          if (provider.isLoading && provider.profile == null) {
            return const Center(child: CircularProgressIndicator());
          }

          if (provider.profile == null) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    provider.error ?? 'Could not load profile.',
                    style: TextStyle(color: Colors.grey.shade600),
                  ),
                  const SizedBox(height: 12),
                  FilledButton(
                    onPressed: provider.fetchProfile,
                    style: AppChrome.primaryButtonStyle(),
                    child: const Text('Retry'),
                  ),
                ],
              ),
            );
          }

          final profile = provider.profile!;

          return ListView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 112),
            children: [
              SpeakardoTopBar(
                title: 'System Settings',
                subtitle: 'Manage your profile and preferences',
                leading: _buildSettingsIcon(),
              ),
              const SizedBox(height: 12),
              if (!profile.emailVerified) ...[
                GlassPanel(
                  borderRadius: 22,
                  color: Colors.amber.withValues(alpha: 0.08),
                  borderColor: Colors.amber.withValues(alpha: 0.25),
                  margin: const EdgeInsets.only(bottom: 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: const [
                          Icon(Icons.warning_amber_rounded, color: Colors.amber),
                          SizedBox(width: 10),
                          Text(
                            'Verify your email',
                            style: TextStyle(
                              color: AppChrome.ink,
                              fontWeight: FontWeight.w800,
                              fontSize: 15,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Check your inbox for a verification link, or resend it below.',
                        style: TextStyle(
                          color: AppChrome.muted,
                          fontSize: 13,
                          height: 1.35,
                        ),
                      ),
                      const SizedBox(height: 12),
                      FilledButton.tonal(
                        onPressed: provider.isSaving
                            ? null
                            : () async {
                                final err = await context
                                    .read<AuthProvider>()
                                    .resendVerificationEmail();
                                if (!mounted) return;
                                if (err != null) {
                                  _showError(err);
                                } else {
                                  _showSuccess(
                                    'Verification email sent.',
                                  );
                                }
                              },
                        child: const Text('Resend verification email'),
                      ),
                    ],
                  ),
                ),
              ],
              _sectionHeader('Account'),
              const SizedBox(height: 8),
              GlassPanel(
                borderRadius: 24,
                padding: EdgeInsets.zero,
                child: ListTile(
                  leading: const Icon(Icons.email_outlined, color: AppChrome.primary),
                  title: const Text(
                    'Email',
                    style: TextStyle(
                      color: AppChrome.ink,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  subtitle: Text(
                    profile.email,
                    style: const TextStyle(color: AppChrome.muted),
                  ),
                  trailing: profile.emailVerified
                      ? const Icon(
                          Icons.verified,
                          color: AppChrome.accent,
                          size: 22,
                        )
                      : const Text(
                          'Unverified',
                          style: TextStyle(
                            color: Colors.amber,
                            fontWeight: FontWeight.w700,
                            fontSize: 12,
                          ),
                        ),
                ),
              ),
              _sectionHeader('Preferences'),
              const SizedBox(height: 8),
              GlassPanel(
                borderRadius: 24,
                padding: EdgeInsets.zero,
                child: SwitchListTile.adaptive(
                  secondary: const Icon(Icons.notifications_outlined, color: AppChrome.primary),
                  title: const Text(
                    'Push notifications',
                    style: TextStyle(
                      color: AppChrome.ink,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  subtitle: const Text(
                    'Receive alerts when reminders are due',
                    style: TextStyle(color: AppChrome.muted),
                  ),
                  value: profile.notificationsEnabled,
                  onChanged: provider.isSaving
                      ? null
                      : (value) async {
                          final ok =
                              await provider.setNotificationsEnabled(value);
                          if (!mounted) return;
                          if (!ok) {
                            _showError('Could not update notification setting.');
                          }
                        },
                ),
              ),
              // --- Timezone (hidden — Option A uses device local time) ---
              // ListTile(
              //   leading: const Icon(Icons.schedule_outlined),
              //   title: const Text('Timezone'),
              //   subtitle: Text(profile.timezone),
              //   trailing: provider.isSaving
              //       ? const SizedBox(
              //           width: 20,
              //           height: 20,
              //           child: CircularProgressIndicator(strokeWidth: 2),
              //         )
              //       : const Icon(Icons.chevron_right),
              //   onTap: provider.isSaving ? null : () => _pickTimezone(provider),
              // ),
              // Padding(
              //   padding: const EdgeInsets.symmetric(horizontal: 16),
              //   child: OutlinedButton.icon(
              //     onPressed: provider.isSaving
              //         ? null
              //         : () async {
              //             final ok = await provider.useDeviceTimezone();
              //             if (!mounted) return;
              //             if (!ok) {
              //               _showError('Could not set device timezone.');
              //             }
              //           },
              //     icon: const Icon(Icons.my_location_outlined),
              //     label: const Text('Use device timezone'),
              //   ),
              // ),
              _sectionHeader('Support & Feedback'),
              const SizedBox(height: 8),
              GlassPanel(
                borderRadius: 24,
                padding: EdgeInsets.zero,
                child: Column(
                  children: [
                    ListTile(
                      leading: const Icon(Icons.rate_review_outlined, color: AppChrome.primary),
                      title: const Text(
                        'Send feedback',
                        style: TextStyle(
                          color: AppChrome.ink,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      subtitle: const Text(
                        'Help us improve the app',
                        style: TextStyle(color: AppChrome.muted),
                      ),
                      trailing: _isSubmittingFeedback
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.chevron_right_rounded, color: AppChrome.muted),
                      onTap: _isSubmittingFeedback ? null : _showFeedbackForm,
                    ),
                    const Divider(
                      height: 1,
                      indent: 56,
                      endIndent: 16,
                      color: AppChrome.line,
                    ),
                    ListTile(
                      leading: const Icon(Icons.mail_outline, color: AppChrome.primary),
                      title: const Text(
                        'Contact support',
                        style: TextStyle(
                          color: AppChrome.ink,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      subtitle: const Text(
                        'support@aireminder.app',
                        style: TextStyle(color: AppChrome.muted),
                      ),
                      trailing: const Icon(
                        Icons.open_in_new_rounded,
                        color: AppChrome.muted,
                        size: 20,
                      ),
                      onTap: _contactSupport,
                    ),
                    const Divider(
                      height: 1,
                      indent: 56,
                      endIndent: 16,
                      color: AppChrome.line,
                    ),
                    ListTile(
                      leading: const Icon(Icons.info_outline, color: AppChrome.primary),
                      title: const Text(
                        'App version',
                        style: TextStyle(
                          color: AppChrome.ink,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      subtitle: Text(
                        _packageInfo == null
                            ? 'Loading...'
                            : '${_packageInfo!.version} (${_packageInfo!.buildNumber})',
                        style: const TextStyle(color: AppChrome.muted),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
              GlassPanel(
                borderRadius: 24,
                padding: EdgeInsets.zero,
                color: Colors.redAccent.withValues(alpha: 0.08),
                borderColor: Colors.redAccent.withValues(alpha: 0.22),
                child: ListTile(
                  leading: const Icon(Icons.logout_rounded, color: Colors.redAccent),
                  title: const Text(
                    'Sign out',
                    style: TextStyle(
                      color: Colors.redAccent,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  onTap: () => context.read<AuthProvider>().logout(),
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
