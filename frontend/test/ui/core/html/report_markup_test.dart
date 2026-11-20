// Tests for the report markup reader: the three-paragraph report with its
// emphasis, escaped text, and the untrusted input it must neutralise (no
// attributes, links, media or scripts reach the text).
import 'package:delphos_frontend/ui/core/html/report_markup.dart';
import 'package:flutter_test/flutter_test.dart';

String plain(List<List<ReportRun>> paragraphs) =>
    [for (final p in paragraphs) p.map((r) => r.text).join()].join('|');

void main() {
  test('reads paragraphs with bold and italic runs', () {
    final paragraphs = parseReportMarkup(
      '<p><strong>Valoración.</strong> Texto con <em>énfasis</em>.</p>'
      '<p>Segundo.</p>',
    );

    expect(paragraphs, hasLength(2));
    expect(paragraphs[0].first, (
      text: 'Valoración.',
      bold: true,
      italic: false,
    ));
    expect(paragraphs[0][1].bold, isFalse);
    expect(paragraphs[0][2], (text: 'énfasis', bold: false, italic: true));
    expect(plain(paragraphs), 'Valoración. Texto con énfasis.|Segundo.');
  });

  test('unescapes entities once, never into markup', () {
    final paragraphs = parseReportMarkup(
      '<p>D&#x27;Arcy &amp; Co &lt;b&gt; &amp;lt; &#39;x&#39; &nbsp;fin</p>',
    );

    expect(plain(paragraphs), "D'Arcy & Co <b> &lt; 'x'  fin");
  });

  test('an invalid numeric entity stays as written', () {
    expect(
      plain(parseReportMarkup('<p>&#0; &#xD800; &#99999999;</p>')),
      '&#0; &#xD800; &#99999999;',
    );
  });

  test('br is a line break inside the paragraph', () {
    expect(plain(parseReportMarkup('<p>uno<br>dos</p>')), 'uno\ndos');
  });

  test('drops attributes, links, media and scripts', () {
    final paragraphs = parseReportMarkup(
      '<p onclick=x>a<img src=//evil>b<a href=javascript:1>t</a>'
      '<script>alert(1)</script><style>p{}</style>'
      '<iframe src=x>dentro</iframe><!-- nota -->c</p>',
    );

    expect(plain(paragraphs), 'abtc');
  });

  test('unwraps unknown tags to their text and ignores stray closers', () {
    expect(
      plain(
        parseReportMarkup('<div><span>uno</span></div></strong><p>dos</p>'),
      ),
      'uno|dos',
    );
    final runs = parseReportMarkup('</strong></em><p>x</p>').single;
    expect(runs.single.bold, isFalse);
  });

  test('text outside paragraphs and empty paragraphs', () {
    expect(plain(parseReportMarkup('suelto<p> </p><p>uno</p>')), 'suelto|uno');
    expect(parseReportMarkup(''), isEmpty);
  });

  test('reads at most reportMarkupLimit units', () {
    final long = '<p>${'a' * (reportMarkupLimit * 2)}</p>';

    expect(plain(parseReportMarkup(long)).length, lessThan(reportMarkupLimit));
  });

  test('an unclosed script never leaks its body as text', () {
    expect(plain(parseReportMarkup('<p>a</p><script>alert(1)<p>b</p>')), 'a');
    expect(plain(parseReportMarkup('<p>a</p><style>p{color:red')), 'a');
  });

  test('a truncated script or closing tag leaks nothing', () {
    expect(plain(parseReportMarkup('<p>a</p><script>alert(')), 'a');
    expect(plain(parseReportMarkup('<p>a</p><script>x</scr')), 'a');
  });

  test('a closed script is skipped and the text after it is kept', () {
    expect(plain(parseReportMarkup('<p>a<SCRIPT>x</SCRIPT >b</p>')), 'ab');
  });

  test('many unclosed openers finish quickly', () {
    final watch = Stopwatch()..start();
    parseReportMarkup('<script>' * 5000);
    parseReportMarkup('<style>x' * 5000);
    parseReportMarkup('<' * 20000);
    parseReportMarkup('<a ' * 7000);
    parseReportMarkup('<p><em><strong>' * 1500);

    expect(watch.elapsedMilliseconds, lessThan(1000));
  });

  test('control and format characters are stripped', () {
    expect(
      plain(parseReportMarkup('<p>a&#x202E;b&#x200B;c\u202Ed&#173;e&#7;f</p>')),
      'abcdef',
    );
  });

  test('a quote around a greater-than ends the tag early', () {
    // Documented limitation: the rest of the attribute shows as plain text.
    expect(plain(parseReportMarkup('<p title="a>b">c</p>')), 'b">c');
  });
}
