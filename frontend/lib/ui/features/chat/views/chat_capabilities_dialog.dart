/// Pop-up explaining what the conversational scouting agent can do.
library;

import 'package:flutter/widgets.dart';

import '../../../core/theme/delphos_colors.dart';
import '../../../core/theme/delphos_text.dart';
import '../../../core/theme/type_scale.dart';
import '../../../core/widgets/action_button.dart';
import '../../../core/widgets/line_glyph.dart';
import '../../../core/widgets/pressable.dart';

const List<(String, String)> _capabilities = [
  (
    'Búsquedas en lenguaje natural',
    'Localiza jugadores por nombre, club, país, posición, diagnóstico de valoración o arquetipo táctico.',
  ),
  (
    'Valoración y acuerdo entre modelos',
    'Consulta precio de mercado, valor justo estimado y coincidencia entre Random Forest y Árbol de Decisión.',
  ),
  (
    'Comparaciones y reemplazos Moneyball',
    'Contrasta estadísticas de la temporada 2025/26, arquetipos K-Means y candidatos de reemplazo más económicos.',
  ),
  (
    'Seguimiento transparente paso a paso',
    'Muestra en tiempo real y en lenguaje natural cada consulta interna sobre los datos del modelo.',
  ),
];

const List<(String, String)> _samplePrompts = [
  (
    'Extremos infravalorados sub-24',
    'Busca extremos infravalorados menores de 24 años.',
  ),
  (
    'Compara a Harry Kane con reemplazos',
    'Compara la valoración y el rendimiento de Harry Kane con sus reemplazos.',
  ),
  (
    'Resume los 3 arquetipos tácticos',
    'Resume los tres arquetipos tácticos calculados en la plantilla.',
  ),
];

/// Modal card shown on entering `/chat` and reopenable from the chat header.
class ChatCapabilitiesDialog extends StatelessWidget {
  const ChatCapabilitiesDialog({
    super.key,
    required this.onClose,
    required this.onPickPrompt,
  });

  final VoidCallback onClose;
  final ValueChanged<String> onPickPrompt;

  @override
  Widget build(BuildContext context) {
    return Positioned.fill(
      child: Semantics(
        scopesRoute: true,
        explicitChildNodes: true,
        label: 'Capacidades del asistente de scouting',
        child: Container(
          color: DelphosColors.ink.withValues(alpha: 0.35),
          alignment: Alignment.center,
          padding: const EdgeInsets.all(24),
          child: Container(
            width: 580,
            padding: const EdgeInsets.all(22),
            decoration: BoxDecoration(
              color: DelphosColors.surface,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: DelphosColors.rule),
              boxShadow: const [
                BoxShadow(
                  color: DelphosColors.floatShadow,
                  blurRadius: 24,
                  offset: Offset(0, 8),
                ),
              ],
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              spacing: 14,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        '¿Qué puede hacer el asistente de scouting?',
                        style: DelphosText.condensed(size: TypeScale.title),
                      ),
                    ),
                    Pressable(
                      onPressed: onClose,
                      semanticLabel: 'Cerrar ventana de capacidades',
                      borderRadius: 6,
                      builder: (context, hovered) => Container(
                        padding: const EdgeInsets.all(6),
                        decoration: BoxDecoration(
                          color: hovered
                              ? DelphosColors.surfaceSubtle
                              : DelphosColors.surface,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: const LineGlyph.close(),
                      ),
                    ),
                  ],
                ),
                Text(
                  'Formula peticiones en lenguaje natural o pide comparaciones entre jugadores. Todas las respuestas se apoyan únicamente en los datos calculados por los modelos del proyecto.',
                  style: DelphosText.ui(
                    color: DelphosColors.ink2,
                    height: 1.45,
                  ),
                ),
                for (final (title, desc) in _capabilities)
                  _CapabilityRow(title: title, description: desc),
                Container(
                  padding: const EdgeInsets.only(top: 8),
                  decoration: const BoxDecoration(
                    border: Border(top: BorderSide(color: DelphosColors.rule)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    spacing: 8,
                    children: [
                      Text(
                        'Ejemplos rápidos',
                        style: DelphosText.ui(
                          size: TypeScale.secondary,
                          weight: FontWeight.w600,
                          color: DelphosColors.ink3,
                        ),
                      ),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          for (final (label, prompt) in _samplePrompts)
                            ActionButton(
                              label: label,
                              onPressed: () => onPickPrompt(prompt),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
                Align(
                  alignment: Alignment.centerRight,
                  child: ActionButton(
                    label: 'Entendido',
                    primary: true,
                    onPressed: onClose,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _CapabilityRow extends StatelessWidget {
  const _CapabilityRow({required this.title, required this.description});

  final String title;
  final String description;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 10,
      children: [
        Container(
          margin: const EdgeInsets.only(top: 6),
          width: 6,
          height: 6,
          decoration: const BoxDecoration(
            color: DelphosColors.ink,
            shape: BoxShape.circle,
          ),
        ),
        Expanded(
          child: Text.rich(
            TextSpan(
              children: [
                TextSpan(
                  text: '$title: ',
                  style: DelphosText.ui(weight: FontWeight.w600),
                ),
                TextSpan(
                  text: description,
                  style: DelphosText.ui(color: DelphosColors.ink2, height: 1.4),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
