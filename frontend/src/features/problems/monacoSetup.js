import { loader } from "@monaco-editor/react";
import * as monaco from "monaco-editor";
import editorWorker from "monaco-editor/editor/editor.worker?worker";
import cssWorker from "monaco-editor/language/css/css.worker?worker";
import htmlWorker from "monaco-editor/language/html/html.worker?worker";
import jsonWorker from "monaco-editor/language/json/json.worker?worker";
import tsWorker from "monaco-editor/language/typescript/ts.worker?worker";

/**
 * Hands `@monaco-editor/react` the editor from this bundle.
 *
 * Left alone, `@monaco-editor/loader` fetches Monaco from jsDelivr at runtime. That
 * is a network dependency in the middle of the code workspace: on a machine behind
 * a proxy, offline, or on a locked-down network the request never resolves, the
 * editor never becomes ready, and the workspace shows an empty panel with no error
 * anywhere. Bundling it removes that failure mode entirely -- the editor ships with
 * the app, like every other dependency.
 *
 * `MonacoEnvironment` is the other half. Monaco spins up a Web Worker per language
 * for tokenising and type-checking; the bundler has to be told how to build one, or
 * the worker silently fails and the language contributes no highlighting.
 *
 * The worker specifiers above deliberately carry no `esm/vs/` prefix. `monaco-editor`
 * 0.57 declares an `exports` map of `"./*": "./esm/vs/*.js"`, so the package prefix is
 * already part of the mapping and spelling it out resolves to
 * `./esm/vs/esm/vs/editor/editor.worker.js`, which does not exist. The import then
 * fails to resolve, this module never runs, `loader.config` is never reached, and the
 * code workspace renders an empty frame with no editor in it and no error in the page
 * -- the failure is reported only in the terminal running the dev server.
 */
self.MonacoEnvironment = {
  getWorker(_moduleId, label) {
    if (label === "json") return new jsonWorker();
    if (label === "css" || label === "scss" || label === "less") return new cssWorker();
    if (label === "html" || label === "handlebars" || label === "razor") return new htmlWorker();
    if (label === "typescript" || label === "javascript") return new tsWorker();
    return new editorWorker();
  },
};

loader.config({ monaco });

export default monaco;
