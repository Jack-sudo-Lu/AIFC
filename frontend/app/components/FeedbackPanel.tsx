"use client";
import { useState } from "react";
import type { Claim, Result } from "../lib/types";

type FeedbackPanelProps = {
  claim: Claim;
  result: Result;
  onSubmit: (correctedStatus: string, note: string) => void;
  onClose: () => void;
};

export default function FeedbackPanel({ claim, result, onSubmit, onClose }: FeedbackPanelProps) {
  const [status, setStatus] = useState(result.status);
  const [note, setNote] = useState("");

  return (
    <div className="bg-gray-50 p-4 rounded-lg mb-3">
      <select
        className="w-full p-2 border rounded mb-2"
        value={status}
        onChange={(e) => setStatus(e.target.value)}
      >
        <option value="SUPPORTED">SUPPORTED</option>
        <option value="REFUTED">REFUTED</option>
        <option value="NEI">NEI</option>
      </select>
      <input
        className="w-full p-2 border rounded mb-2"
        placeholder="Add a note..."
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />
      <div className="flex gap-2">
        <button
          onClick={() => onSubmit(status, note)}
          className="bg-indigo-500 text-white px-4 py-2 rounded text-sm"
        >
          Submit
        </button>
        <button
          onClick={onClose}
          className="text-gray-500 px-4 py-2 rounded text-sm hover:bg-gray-200"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
