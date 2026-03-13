"use client";

import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";

interface JsonViewerProps {
  data: unknown;
  initialExpand?: boolean;
}

function JsonNode({ data, level = 0 }: { data: unknown; level?: number }) {
  const [expanded, setExpanded] = useState(level < 2);

  if (data === null) {
    return <span className="text-gray-500">null</span>;
  }

  if (data === undefined) {
    return <span className="text-gray-500">undefined</span>;
  }

  if (typeof data === "boolean" || typeof data === "number") {
    return <span className="text-blue-600">{String(data)}</span>;
  }

  if (typeof data === "string") {
    return <span className="text-green-600">"{data}"</span>;
  }

  if (Array.isArray(data)) {
    if (data.length === 0) return <span>[]</span>;

    return (
      <div className="ml-4">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-gray-400 hover:text-gray-600 mr-1"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        <span className="text-gray-500">[</span>
        {expanded && (
          <div className="ml-4">
            {data.map((item, i) => (
              <div key={i} className="border-l border-gray-200 pl-2">
                <JsonNode data={item} level={level + 1} />
                {i < data.length - 1 && <span className="text-gray-500">,</span>}
              </div>
            ))}
          </div>
        )}
        <span className="text-gray-500">]</span>
      </div>
    );
  }

  if (typeof data === "object") {
    const entries = Object.entries(data as Record<string, unknown>);
    if (entries.length === 0) return <span>{"{}"}</span>;

    return (
      <div className="ml-4">
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-gray-400 hover:text-gray-600 mr-1"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
        <span className="text-gray-500">{"{"}</span>
        {expanded && (
          <div className="ml-4">
            {entries.map(([key, value], i) => (
              <div key={key} className="border-l border-gray-200 pl-2">
                <span className="text-purple-600">"{key}"</span>
                <span className="text-gray-500">: </span>
                <JsonNode data={value} level={level + 1} />
                {i < entries.length - 1 && <span className="text-gray-500">,</span>}
              </div>
            ))}
          </div>
        )}
        <span className="text-gray-500">{"}"}</span>
      </div>
    );
  }

  return <span className="text-gray-500">{String(data)}</span>;
}

export function JsonViewer({ data, initialExpand = false }: JsonViewerProps) {
  return (
    <div className="font-mono text-sm bg-gray-50 p-3 rounded-lg overflow-auto max-h-96">
      <JsonNode data={data} />
    </div>
  );
}
