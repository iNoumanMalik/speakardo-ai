import 'package:flutter/material.dart';

import '../widgets/app_chrome.dart';

class MemoryScreen extends StatelessWidget {
  const MemoryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SpeakardoScaffold(
      child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 112),
        children: const [
          SpeakardoTopBar(
            title: 'Memory Core',
            subtitle: 'Private and encrypted',
            leading: _MemoryIcon(),
            trailing: _SearchButton(),
          ),
          SizedBox(height: 18),
          _MemoryOrb(),
          SizedBox(height: 18),
          _StatsGrid(),
          SizedBox(height: 28),
          _SectionTitle(title: 'Active Clusters', action: 'See Map'),
          SizedBox(height: 12),
          _ClusterTile(
            icon: Icons.record_voice_over_rounded,
            title: 'Communication Habits',
            subtitle: 'Updated from chat 2h ago',
            color: AppChrome.primary,
            bars: 4,
          ),
          SizedBox(height: 12),
          _ClusterTile(
            icon: Icons.account_tree_rounded,
            title: 'Project "Nexus" Context',
            subtitle: '42 interconnected insights',
            color: AppChrome.accent,
            bars: 3,
          ),
          SizedBox(height: 12),
          _ClusterTile(
            icon: Icons.favorite_border_rounded,
            title: 'Personal Health',
            subtitle: 'Sleep, workouts, medication cadence',
            color: Color(0xFFEF4444),
            bars: 2,
          ),
          SizedBox(height: 24),
          _MaintenancePanel(),
        ],
      ),
    );
  }
}

class _MemoryIcon extends StatelessWidget {
  const _MemoryIcon();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        color: AppChrome.primary.withValues(alpha: 0.1),
        border: Border.all(color: AppChrome.primary.withValues(alpha: 0.16)),
      ),
      child: const Icon(
        Icons.psychology_alt_rounded,
        color: AppChrome.primary,
      ),
    );
  }
}

class _SearchButton extends StatelessWidget {
  const _SearchButton();

  @override
  Widget build(BuildContext context) {
    return IconButton.filledTonal(
      onPressed: () {},
      icon: const Icon(Icons.search_rounded),
      tooltip: 'Search memory',
      style: IconButton.styleFrom(
        backgroundColor: Colors.white.withValues(alpha: 0.72),
        foregroundColor: AppChrome.muted,
      ),
    );
  }
}

class _MemoryOrb extends StatelessWidget {
  const _MemoryOrb();

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 258,
      child: Stack(
        alignment: Alignment.center,
        children: [
          SizedBox(
            width: 220,
            height: 220,
            child: CircularProgressIndicator(
              value: 0.74,
              strokeWidth: 1,
              color: AppChrome.primary.withValues(alpha: 0.16),
              backgroundColor: AppChrome.accent.withValues(alpha: 0.08),
            ),
          ),
          SizedBox(
            width: 168,
            height: 168,
            child: CircularProgressIndicator(
              value: 0.46,
              strokeWidth: 1,
              color: AppChrome.accent.withValues(alpha: 0.18),
              backgroundColor: AppChrome.primary.withValues(alpha: 0.05),
            ),
          ),
          GlassPanel(
            borderRadius: 80,
            padding: const EdgeInsets.all(22),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: const [
                Icon(
                  Icons.psychology_alt_rounded,
                  size: 52,
                  color: AppChrome.primary,
                ),
                SizedBox(height: 8),
                Text(
                  'Speakardo v2.4',
                  style: TextStyle(
                    color: AppChrome.primary,
                    fontSize: 11,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ],
            ),
          ),
          const Positioned(
            top: 20,
            right: 20,
            child: _FloatingTag(label: 'Q3 Goals', color: AppChrome.accent),
          ),
          const Positioned(
            bottom: 28,
            left: 4,
            child: _FloatingTag(
              label: 'Personal Health',
              color: AppChrome.primary,
            ),
          ),
        ],
      ),
    );
  }
}

class _FloatingTag extends StatelessWidget {
  const _FloatingTag({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      borderRadius: 18,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 7),
          Text(
            label,
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
          ),
        ],
      ),
    );
  }
}

class _StatsGrid extends StatelessWidget {
  const _StatsGrid();

  @override
  Widget build(BuildContext context) {
    return const Row(
      children: [
        Expanded(
          child: _StatPanel(
            label: 'Memories',
            value: '1,284',
            meta: '+12 today',
            icon: Icons.add_circle_outline_rounded,
          ),
        ),
        SizedBox(width: 12),
        Expanded(
          child: _StatPanel(
            label: 'Sync Quality',
            value: '98%',
            meta: 'Stable',
            icon: Icons.bolt_rounded,
          ),
        ),
      ],
    );
  }
}

class _StatPanel extends StatelessWidget {
  const _StatPanel({
    required this.label,
    required this.value,
    required this.meta,
    required this.icon,
  });

  final String label;
  final String value;
  final String meta;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      borderRadius: 22,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label.toUpperCase(),
            style: const TextStyle(
              color: AppChrome.muted,
              fontSize: 11,
              fontWeight: FontWeight.w900,
            ),
          ),
          const SizedBox(height: 6),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                value,
                style: const TextStyle(
                  color: AppChrome.ink,
                  fontSize: 26,
                  fontWeight: FontWeight.w900,
                ),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  meta,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppChrome.accent,
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
              Icon(icon, size: 18, color: AppChrome.primary),
            ],
          ),
        ],
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({required this.title, required this.action});

  final String title;
  final String action;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: const TextStyle(
                color: AppChrome.ink,
                fontSize: 19,
                fontWeight: FontWeight.w800,
              ),
            ),
          ),
          TextButton(onPressed: () {}, child: Text(action.toUpperCase())),
        ],
      ),
    );
  }
}

class _ClusterTile extends StatelessWidget {
  const _ClusterTile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.color,
    required this.bars,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final int bars;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      borderRadius: 24,
      padding: const EdgeInsets.all(14),
      child: Column(
        children: [
          Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(17),
                  color: color.withValues(alpha: 0.1),
                ),
                child: Icon(icon, color: color, size: 26),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppChrome.ink,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppChrome.muted,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right_rounded, color: AppChrome.muted),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: List.generate(4, (index) {
              final active = index < bars;
              return Expanded(
                child: Container(
                  height: 4,
                  margin: EdgeInsets.only(right: index == 3 ? 0 : 5),
                  decoration: BoxDecoration(
                    color: active
                        ? color.withValues(alpha: 1 - (index * 0.18))
                        : color.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              );
            }),
          ),
        ],
      ),
    );
  }
}

class _MaintenancePanel extends StatelessWidget {
  const _MaintenancePanel();

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      borderRadius: 26,
      color: AppChrome.primary.withValues(alpha: 0.06),
      borderColor: AppChrome.primary.withValues(alpha: 0.12),
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.tips_and_updates_rounded, color: AppChrome.primary),
          const SizedBox(height: 12),
          const Text(
            'Memory Maintenance',
            style: TextStyle(
              color: AppChrome.ink,
              fontSize: 18,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'I noticed conflicting information about your Friday schedule. Shall we reconcile it?',
            style: TextStyle(color: AppChrome.muted, height: 1.35),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: () {},
            style: AppChrome.primaryButtonStyle(),
            child: const Text('Optimize Now'),
          ),
        ],
      ),
    );
  }
}
