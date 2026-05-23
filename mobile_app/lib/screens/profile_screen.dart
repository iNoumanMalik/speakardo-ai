import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/auth_provider.dart';
import '../services/profile_provider.dart';
import '../utils/timezone_options.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({Key? key}) : super(key: key);

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  PackageInfo? _packageInfo;

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

  void _showFaq() {
    showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('FAQ'),
        content: const SingleChildScrollView(
          child: Text(
            'How do I create a reminder?\n'
            'Open the Chat tab and type or speak naturally, e.g. '
            '"Remind me to take medicine at 9 PM". Confirm when prompted.\n\n'
            'How do notifications work?\n'
            'Enable push notifications in Profile and allow permission when asked. '
            'Reminders fire at the scheduled time in your selected timezone.\n\n'
            'Can I turn notifications off?\n'
            'Yes. Use the Push notifications toggle in Profile. '
            'Reminders still appear in your list.',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

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

  Future<void> _pickTimezone(ProfileProvider provider) async {
    final options = timezoneOptionsFor(provider.timezone);
    final selected = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (context) {
        return DraggableScrollableSheet(
          expand: false,
          initialChildSize: 0.6,
          minChildSize: 0.4,
          maxChildSize: 0.9,
          builder: (context, scrollController) {
            return Column(
              children: [
                const Padding(
                  padding: EdgeInsets.all(16),
                  child: Text(
                    'Select timezone',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                Expanded(
                  child: ListView.builder(
                    controller: scrollController,
                    itemCount: options.length,
                    itemBuilder: (context, index) {
                      final tz = options[index];
                      final selectedTz = tz == provider.timezone;
                      return ListTile(
                        title: Text(tz),
                        trailing: selectedTz
                            ? const Icon(Icons.check, color: Color(0xFF6750A4))
                            : null,
                        onTap: () => Navigator.pop(context, tz),
                      );
                    },
                  ),
                ),
              ],
            );
          },
        );
      },
    );

    if (selected == null || selected == provider.timezone) return;

    final ok = await provider.setTimezone(selected);
    if (!mounted) return;
    if (!ok) {
      _showError('Could not update timezone.');
    }
  }

  Widget _sectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 20, 20, 8),
      child: Text(
        title,
        style: const TextStyle(
          fontSize: 13,
          fontWeight: FontWeight.w700,
          color: Color(0xFF6750A4),
          letterSpacing: 0.5,
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        centerTitle: true,
      ),
      body: Consumer<ProfileProvider>(
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
                    child: const Text('Retry'),
                  ),
                ],
              ),
            );
          }

          final profile = provider.profile!;

          return ListView(
            children: [
              _sectionHeader('ACCOUNT'),
              ListTile(
                leading: const Icon(Icons.email_outlined),
                title: const Text('Email'),
                subtitle: Text(profile.email),
              ),
              _sectionHeader('PREFERENCES'),
              SwitchListTile(
                secondary: const Icon(Icons.notifications_outlined),
                title: const Text('Push notifications'),
                subtitle: const Text(
                  'Receive alerts when reminders are due',
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
              ListTile(
                leading: const Icon(Icons.schedule_outlined),
                title: const Text('Timezone'),
                subtitle: Text(profile.timezone),
                trailing: provider.isSaving
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.chevron_right),
                onTap: provider.isSaving ? null : () => _pickTimezone(provider),
              ),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: OutlinedButton.icon(
                  onPressed: provider.isSaving
                      ? null
                      : () async {
                          final ok = await provider.useDeviceTimezone();
                          if (!mounted) return;
                          if (!ok) {
                            _showError('Could not set device timezone.');
                          }
                        },
                  icon: const Icon(Icons.my_location_outlined),
                  label: const Text('Use device timezone'),
                ),
              ),
              _sectionHeader('SUPPORT'),
              ListTile(
                leading: const Icon(Icons.help_outline),
                title: const Text('FAQ'),
                trailing: const Icon(Icons.chevron_right),
                onTap: _showFaq,
              ),
              ListTile(
                leading: const Icon(Icons.mail_outline),
                title: const Text('Contact support'),
                subtitle: const Text('support@aireminder.app'),
                trailing: const Icon(Icons.open_in_new),
                onTap: _contactSupport,
              ),
              ListTile(
                leading: const Icon(Icons.info_outline),
                title: const Text('App version'),
                subtitle: Text(
                  _packageInfo == null
                      ? 'Loading...'
                      : '${_packageInfo!.version} (${_packageInfo!.buildNumber})',
                ),
              ),
              const Divider(height: 32),
              ListTile(
                leading: Icon(
                  Icons.logout,
                  color: Theme.of(context).colorScheme.error,
                ),
                title: Text(
                  'Sign out',
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                onTap: () => context.read<AuthProvider>().logout(),
              ),
              const SizedBox(height: 24),
            ],
          );
        },
      ),
    );
  }
}
