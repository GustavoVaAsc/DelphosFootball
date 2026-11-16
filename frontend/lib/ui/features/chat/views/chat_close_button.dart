/// The pop-up's close button, in the dossier close button's 32 px style.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_radius.dart';
import '../../../core/theme/motion.dart';
import '../../../core/widgets/line_glyph.dart';
import '../../../core/widgets/pressable.dart';

/// A 32 x 32 bordered icon button with the 14 px ×.
class ChatCloseButton extends StatelessWidget {
  const ChatCloseButton({
    super.key,
    required this.onPressed,
    required this.focusNode,
  });

  final VoidCallback onPressed;
  final FocusNode focusNode;

  @override
  Widget build(BuildContext context) {
    return Pressable(
      onPressed: onPressed,
      focusNode: focusNode,
      semanticLabel: 'Cerrar ventana de capacidades',
      borderRadius: DelphosRadius.control,
      builder: (context, hovered) => AnimatedContainer(
        duration: DelphosMotion.duration(context, DelphosMotion.hover),
        curve: DelphosMotion.easeOut,
        width: 32,
        height: 32,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: hovered ? DelphosColors.surfaceSubtle : DelphosColors.surface,
          borderRadius: BorderRadius.circular(DelphosRadius.control),
          border: Border.all(
            color: hovered ? DelphosColors.ink2 : DelphosColors.controlBorder,
          ),
        ),
        child: const LineGlyph.close(),
      ),
    );
  }
}
