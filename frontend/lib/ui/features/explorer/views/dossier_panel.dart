/// The player dossier (DESIGN.md §4): a fixed header with the identity and
/// the one action, "Cerrar ficha", then the scrolling body with the
/// valuation, the season, the replacements and the summary.
///
/// Motion (DESIGN.md §5): opening and closing are instant. When one loaded
/// player replaces another inside the open dossier, the content enters with
/// the preview's `dossierEnter` (opacity 0.65 to 1 and 3 px up, 180 ms) to
/// mark that the panel now shows someone else. Instant under reduced
/// motion. Sections also fade in once as their data arrives (FadeInOnce).
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/motion.dart';

import 'package:provider/provider.dart';

import '../../../core/view_models/dataset_view_model.dart';
import '../../../core/view_models/section_status.dart';
import '../view_models/dossier_view_model.dart';
import 'dossier_body.dart';
import 'dossier_close_button.dart';
import 'dossier_header.dart';
import 'dossier_header_skeleton.dart';
import 'dossier_load_error.dart';

/// The dossier card, shown beside the table or as its own page.
class DossierPanel extends StatefulWidget {
  const DossierPanel({super.key, required this.vm, required this.onClose});

  final DossierViewModel vm;
  final VoidCallback onClose;

  @override
  State<DossierPanel> createState() => _DossierPanelState();
}

class _DossierPanelState extends State<DossierPanel>
    with SingleTickerProviderStateMixin {
  late final AnimationController _swap = AnimationController(
    vsync: this,
    value: 1,
  );
  late final Animation<double> _curve = CurvedAnimation(
    parent: _swap,
    curve: DelphosMotion.easeOut,
  );
  late int? _shownId = widget.vm.profile?.id;

  @override
  void didUpdateWidget(DossierPanel oldWidget) {
    super.didUpdateWidget(oldWidget);
    final id = widget.vm.profile?.id;
    if (id == null || id == _shownId) return;
    if (_shownId != null) {
      _swap.duration = DelphosMotion.duration(
        context,
        DelphosMotion.dossierSwap,
      );
      _swap.forward(from: 0);
    }
    _shownId = id;
  }

  @override
  void dispose() {
    _swap.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final vm = widget.vm;
    final profile = vm.profile;
    final overview = context.watch<DatasetViewModel?>()?.overview;
    final identity = switch (vm.identity.status) {
      SectionStatus.ready when profile != null => DossierHeader(
        profile: profile,
        eliteAsset: vm.replacements.value?.isEliteAsset ?? false,
        dataDate: overview?.asOfDate,
      ),
      SectionStatus.loading => const DossierHeaderSkeleton(),
      _ => DossierLoadError(onRetry: vm.retry),
    };
    final content = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.fromLTRB(20, 16, 20, 14),
          decoration: const BoxDecoration(
            border: Border(bottom: BorderSide(color: DelphosColors.rule)),
          ),
          child: identity,
        ),
        Expanded(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
            child: DossierBody(vm: vm, datasetSeason: overview?.season),
          ),
        ),
      ],
    );
    return Semantics(
      container: true,
      label: profile == null ? 'Ficha' : 'Ficha de ${profile.name}',
      child: Container(
        decoration: BoxDecoration(
          color: DelphosColors.surface,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: DelphosColors.rule),
        ),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(9),
          // The close button sits inside the card's corner with room for
          // its 2 px ring offset, outside the clipped, animated content.
          child: Stack(
            children: [
              Positioned.fill(
                child: FadeTransition(
                  opacity: Tween<double>(begin: 0.65, end: 1).animate(_curve),
                  child: AnimatedBuilder(
                    animation: _curve,
                    builder: (context, child) => Transform.translate(
                      offset: Offset(0, 3 * (1 - _curve.value)),
                      child: child,
                    ),
                    child: content,
                  ),
                ),
              ),
              Positioned(
                top: 12,
                right: 12,
                child: DossierCloseButton(onPressed: widget.onClose),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
