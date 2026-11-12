{{flutter_js}}
{{flutter_build_config}}

// DelphosFootball bootstrap (ADR-026). The build runs with
// --no-web-resources-cdn, so CanvasKit loads from this origin's canvaskit/.
// The engine's fallback fonts load from fonts-fallback/ on this origin
// instead of fonts.gstatic.com: only Roboto is bundled there, so a glyph
// that Archivo, Source Serif 4 and Roboto lack renders as a missing glyph
// instead of fetching a Noto font from Google.

// Remove the static loading line of index.html once Flutter has painted.
window.addEventListener(
  "flutter-first-frame",
  function () {
    var loading = document.getElementById("app-loading");
    if (loading) {
      loading.remove();
    }
  },
  { once: true }
);

_flutter.loader.load({
  config: {
    fontFallbackBaseUrl: "fonts-fallback/",
  },
});
