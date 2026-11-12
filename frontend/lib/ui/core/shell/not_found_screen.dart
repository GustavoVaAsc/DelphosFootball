/// The page for a path the app does not know: one sentence and a way back.
/// It renders without the shell, so a broken link never shows a module as
/// active.
library;

import 'package:go_router/go_router.dart';
import 'package:material_ui/material_ui.dart';

import '../../../routing/routes.dart';
import '../theme/delphos_colors.dart';
import '../theme/delphos_text.dart';
import '../theme/type_scale.dart';
import '../widgets/text_link.dart';

/// Shown by the router for an unknown path.
class NotFoundScreen extends StatelessWidget {
  const NotFoundScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Title(
      title: Routes.appTitle,
      color: DelphosColors.ink,
      child: Scaffold(
        backgroundColor: DelphosColors.canvas,
        body: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            spacing: 12,
            children: [
              Text(
                'Esta dirección no existe.',
                style: DelphosText.ui(
                  size: TypeScale.title,
                  weight: FontWeight.w700,
                ),
              ),
              TextLink(
                label: 'Ir al Explorador de Mercado',
                onPressed: () => context.go(Routes.explorer),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
