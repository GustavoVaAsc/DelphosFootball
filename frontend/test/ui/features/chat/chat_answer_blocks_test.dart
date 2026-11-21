// Unit and widget checks for PitIA's Markdown block and inline formatting.
import 'package:delphos_frontend/ui/features/chat/views/chat_answer.dart';
import 'package:delphos_frontend/ui/features/chat/views/chat_answer_blocks.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';

import '../../../support/app_harness.dart';

void main() {
  test('parses headings, bullets, numbered items and paragraphs cleanly', () {
    const source = '''
### **Resumen de mercado**

Primera línea de análisis.
Segunda línea unida al párrafo.

- **Pau Cubarsí**: central sub-20.
* **Lamine Yamal**: extremo derecho.

1. Valorado por debajo de su nivel.
2. Alta proyección de titularidad.
''';

    final blocks = parseChatAnswerBlocks(source);
    expect(blocks.map((b) => b.kind), [
      ChatBlockKind.heading,
      ChatBlockKind.paragraph,
      ChatBlockKind.bullet,
      ChatBlockKind.bullet,
      ChatBlockKind.numbered,
      ChatBlockKind.numbered,
    ]);
    expect(blocks[0].text, 'Resumen de mercado');
    expect(
      blocks[1].text,
      'Primera línea de análisis.\nSegunda línea unida al párrafo.',
    );
    expect(blocks[2].text, '**Pau Cubarsí**: central sub-20.');
    expect(blocks[4].marker, '1.');
    expect(blocks[5].marker, '2.');
  });

  test(
    'parses bold and italic inline runs without breaking on stray asterisks',
    () {
      final runs = parseChatInlineRuns(
        'Precio: **€70,0 M** con *alta eficiencia* y 2 * 3 **sin cerrar',
      );
      expect(runs.length, 5);
      expect(runs[0].text, 'Precio: ');
      expect(runs[0].bold || runs[0].italic, isFalse);
      expect(runs[1].text, '€70,0 M');
      expect(runs[1].bold, isTrue);
      expect(runs[2].text, ' con ');
      expect(runs[3].text, 'alta eficiencia');
      expect(runs[3].italic, isTrue);
      expect(runs[4].text, ' y 2 * 3 **sin cerrar');
      expect(runs[4].bold || runs[4].italic, isFalse);
    },
  );

  testWidgets(
    'renders structured headings, bullets and numbers inside ChatAnswer',
    (tester) async {
      await loadArchivo();
      await tester.pumpWidget(
        const MediaQuery(
          data: MediaQueryData(),
          child: Directionality(
            textDirection: TextDirection.ltr,
            child: SizedBox(
              width: 600,
              child: ChatAnswer(
                text: '## Diagnóstico\n\n- **Cubarsí** es clave.\n1. Coste competitivo.',
              ),
            ),
          ),
        ),
      );

      expect(find.text('Diagnóstico', findRichText: true), findsOneWidget);
      expect(find.text('•'), findsOneWidget);
      expect(find.text('1.'), findsOneWidget);
      expect(
        find.textContaining('Cubarsí es clave.', findRichText: true),
        findsOneWidget,
      );
    },
  );
}
