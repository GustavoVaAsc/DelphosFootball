/// The title block of an archetype card: the long name and the one-line
/// description (DESIGN.md §3 and §4).
library;

import 'package:flutter/widgets.dart';

import '../../../core/labels/archetypes.dart';
import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';

/// The long name at 20/700 and the one-sentence description.
class ArchetypeHeading extends StatelessWidget {
  const ArchetypeHeading({super.key, required this.clusterId});

  final int clusterId;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    spacing: 4,
    children: [
      Semantics(
        header: true,
        child: Text(
          archetypeLongName(clusterId) ?? '',
          style: DelphosText.ui(
            size: TypeScale.title,
            weight: FontWeight.w700,
            height: 1.2,
          ),
        ),
      ),
      if (archetypeDescription(clusterId) case final description?)
        Text(
          description,
          style: DelphosText.ui(color: DelphosColors.ink2, height: 1.5),
        ),
    ],
  );
}
