"use client";
import { useState, useCallback, useEffect } from "react";
import type { HistoryItem } from "../lib/types";
import { fetchHistory } from "../lib/api";

export function useHistory() {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const limit = 20;

  const load = useCallback(async (reset = false) => {
    setLoading(true);
    try {
      const newOffset = reset ? 0 : offset;
      const data = await fetchHistory(limit, newOffset);
      if (reset) {
        setItems(data.items);
        setOffset(data.items.length);
      } else {
        setItems((prev) => [...prev, ...data.items]);
        setOffset((prev) => prev + data.items.length);
      }
      setTotal(data.total);
    } catch (e) {
      console.error("Failed to load history:", e);
    } finally {
      setLoading(false);
    }
  }, [offset]);

  const refresh = useCallback(() => load(true), [load]);

  const loadMore = useCallback(() => {
    if (!loading && items.length < total) {
      load(false);
    }
  }, [loading, items.length, total, load]);

  // Load on mount
  useEffect(() => {
    load(true);
  }, []);

  return {
    items,
    total,
    loading,
    hasMore: items.length < total,
    refresh,
    loadMore,
  };
}
