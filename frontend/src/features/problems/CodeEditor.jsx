import Editor from "@monaco-editor/react";

export default function CodeEditor({ value, language, onChange }) {
  return (
    <div className="editor-frame">
      <Editor
        defaultLanguage={language}
        language={language}
        onChange={(nextValue) => onChange(nextValue || "")}
        options={{
          automaticLayout: true,
          fontFamily: "'JetBrains Mono', 'SFMono-Regular', Consolas, monospace",
          fontSize: 13,
          minimap: { enabled: false },
          padding: { top: 18, bottom: 18 },
          scrollBeyondLastLine: false,
          smoothScrolling: true,
          tabSize: 2,
        }}
        theme="vs-dark"
        value={value}
      />
    </div>
  );
}
