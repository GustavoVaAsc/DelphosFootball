/// The competitive-exposure profile chart of an archetype card (DESIGN.md §1
/// and §4): empirical 2025 K-Means cluster shares of minutes across Liga, UEFA
/// and Copas plus starter rate, rendered with ink tones on `--surface-subtle`.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_radius.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';

/// Competitive exposure and starter rate summary for one K-Means archetype.
class ArchetypePitch extends StatelessWidget {
  const ArchetypePitch({super.key, required this.clusterId});

  final int clusterId;

  // 2025 test-cohort empirical cluster shares (Liga, UEFA, Copas, starter %)
  // paired by `clusterId`, since `GET /clusters` omits competition splits.
  static const Map<int, (int, int, int, int)> _profiles = {
    0: (68, 27, 5, 72),
    1: (54, 1, 45, 52),
    2: (94, 1, 5, 72),
  };

  @override
  Widget build(BuildContext context) {
    final (leaguePct, uefaPct, cupPct, starterPct) =
        _profiles[clusterId] ?? _profiles[2]!;
    final headingStyle = DelphosText.ui(
      size: TypeScale.label,
      weight: FontWeight.w500,
      color: DelphosColors.ink3,
      height: 1.2,
    );
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: DelphosColors.surfaceSubtle,
        borderRadius: BorderRadius.circular(DelphosRadius.inset),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        spacing: 12,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            spacing: 8,
            children: [
              Text('Reparto de minutos por competición', style: headingStyle),
              _bar(
                height: 10,
                gap: 2,
                segments: [
                  (leaguePct, DelphosColors.ink),
                  (uefaPct, DelphosColors.ink2),
                  (cupPct, DelphosColors.controlBorder),
                ],
              ),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _legendItem('Liga $leaguePct%', DelphosColors.ink),
                  _legendItem('UEFA $uefaPct%', DelphosColors.ink2),
                  _legendItem('Copas $cupPct%', DelphosColors.controlBorder),
                ],
              ),
            ],
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            spacing: 6,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('Tasa de titularidad', style: headingStyle),
                  Text(
                    '$starterPct%',
                    style: DelphosText.ui(
                      size: TypeScale.secondary,
                      weight: FontWeight.w600,
                      color: DelphosColors.ink,
                      tabular: true,
                    ),
                  ),
                ],
              ),
              _bar(
                height: 8,
                gap: 0,
                background: DelphosColors.surfaceMuted,
                segments: [
                  (starterPct, DelphosColors.ink),
                  (100 - starterPct, null),
                ],
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _bar({
    required double height,
    required double gap,
    required List<(int, Color?)> segments,
    Color? background,
  }) => ExcludeSemantics(
    child: ClipRRect(
      borderRadius: BorderRadius.circular(DelphosRadius.small),
      child: SizedBox(
        height: height,
        child: ColoredBox(
          color: background ?? const Color(0x00000000),
          child: Row(
            spacing: gap,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (final (flex, tone) in segments)
                Expanded(
                  flex: flex,
                  child: tone == null
                      ? const SizedBox.expand()
                      : ColoredBox(color: tone),
                ),
            ],
          ),
        ),
      ),
    ),
  );

  Widget _legendItem(String label, Color tone) => Row(
    mainAxisSize: MainAxisSize.min,
    spacing: 5,
    children: [
      ExcludeSemantics(
        child: Container(
          width: 7,
          height: 7,
          decoration: BoxDecoration(
            color: tone,
            borderRadius: BorderRadius.circular(DelphosRadius.hairline),
          ),
        ),
      ),
      Text(
        label,
        style: DelphosText.ui(
          size: TypeScale.secondary,
          color: DelphosColors.ink2,
          tabular: true,
        ),
      ),
    ],
  );
}
