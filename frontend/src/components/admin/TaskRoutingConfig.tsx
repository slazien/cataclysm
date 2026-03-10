"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  getLlmModels,
  getLlmTaskRoutes,
  setLlmTaskRoute,
  deleteLlmTaskRoute,
  type LlmModelInfo,
  type LlmRouteEntry,
} from "@/lib/admin-api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

// Provider color map
const PROVIDER_COLORS: Record<string, string> = {
  anthropic: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  openai: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
  google: "bg-blue-500/20 text-blue-400 border-blue-500/30",
};

function getModelDisplay(models: LlmModelInfo[], entry: LlmRouteEntry): string {
  const found = models.find((m) => m.provider === entry.provider && m.model === entry.model);
  return found?.display ?? entry.model;
}

function getModelCost(models: LlmModelInfo[], entry: LlmRouteEntry): string {
  const found = models.find((m) => m.provider === entry.provider && m.model === entry.model);
  if (!found) return "";
  return `$${found.cost_in}/${found.cost_out}`;
}

// SortableItem for each chain entry
function SortableChainEntry({
  id,
  entry,
  models,
  availableProviders,
  onRemove,
}: {
  id: string;
  entry: LlmRouteEntry;
  models: LlmModelInfo[];
  availableProviders: string[];
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition };
  const hasKey = availableProviders.includes(entry.provider);
  const colors = PROVIDER_COLORS[entry.provider] ?? "bg-slate-500/20 text-slate-400";

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-2 rounded-md border px-2 py-1.5 text-sm ${
        hasKey
          ? "border-slate-700/60 bg-slate-800/50"
          : "border-slate-700/30 bg-slate-800/20 opacity-50"
      }`}
    >
      <button
        {...attributes}
        {...listeners}
        className="cursor-grab text-slate-500 hover:text-slate-300"
        aria-label="Drag to reorder"
      >
        ☰
      </button>
      <Badge variant="outline" className={`text-xs ${colors}`}>
        {entry.provider}
      </Badge>
      <span className="text-slate-100">{getModelDisplay(models, entry)}</span>
      <span className="text-xs text-slate-500">{getModelCost(models, entry)}</span>
      {!hasKey && (
        <Badge variant="outline" className="border-red-500/30 bg-red-500/10 text-xs text-red-400">
          No key
        </Badge>
      )}
      <button
        onClick={onRemove}
        className="ml-auto text-slate-500 hover:text-red-400"
        aria-label="Remove"
      >
        ×
      </button>
    </div>
  );
}

// Simple dropdown for adding a model
function AddModelDropdown({
  models,
  availableProviders,
  onSelect,
}: {
  models: LlmModelInfo[];
  availableProviders: string[];
  onSelect: (model: LlmModelInfo) => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <Button size="xs" variant="outline" onClick={() => setOpen(!open)} className="text-xs">
        + Add model
      </Button>
      {open && (
        <div className="absolute left-0 top-full z-10 mt-1 w-64 rounded-md border border-slate-700 bg-slate-900 py-1 shadow-lg">
          {models.map((m) => {
            const hasKey = availableProviders.includes(m.provider);
            const colors = PROVIDER_COLORS[m.provider] ?? "";
            return (
              <button
                key={`${m.provider}-${m.model}`}
                onClick={() => {
                  onSelect(m);
                  setOpen(false);
                }}
                disabled={!hasKey}
                className={`flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm hover:bg-slate-800 ${
                  hasKey ? "text-slate-100" : "text-slate-500 opacity-50"
                }`}
              >
                <Badge variant="outline" className={`text-xs ${colors}`}>
                  {m.provider}
                </Badge>
                <span>{m.display}</span>
                <span className="ml-auto text-xs text-slate-500">
                  ${m.cost_in}/{m.cost_out}
                </span>
                {!hasKey && <span className="text-xs text-red-400">No key</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// Single task row
function TaskRow({
  task,
  chain,
  models,
  availableProviders,
  onSave,
  onDelete,
}: {
  task: string;
  chain: LlmRouteEntry[] | null;
  models: LlmModelInfo[];
  availableProviders: string[];
  onSave: (chain: LlmRouteEntry[]) => void;
  onDelete: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const configured = chain !== null && chain.length > 0;
  const currentChain = chain ?? [];

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = currentChain.findIndex((_, i) => `${task}-${i}` === active.id);
    const newIndex = currentChain.findIndex((_, i) => `${task}-${i}` === over.id);
    if (oldIndex === -1 || newIndex === -1) return;
    onSave(arrayMove([...currentChain], oldIndex, newIndex));
  }

  function handleRemove(index: number) {
    const newChain = currentChain.filter((_, i) => i !== index);
    if (newChain.length === 0) onDelete();
    else onSave(newChain);
  }

  function handleAdd(model: LlmModelInfo) {
    onSave([...currentChain, { provider: model.provider, model: model.model }]);
  }

  // Models not already in the chain
  const availableModels = models.filter(
    (m) => !currentChain.some((e) => e.provider === m.provider && e.model === m.model),
  );

  const primaryDisplay = configured ? getModelDisplay(models, currentChain[0]) : "Default";

  return (
    <div className="border-b border-slate-800/60 last:border-b-0">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm hover:bg-slate-800/30"
      >
        <span className="text-xs text-slate-500">{expanded ? "▼" : "▶"}</span>
        <span className="font-medium text-slate-100">{task}</span>
        <span className="ml-auto text-xs text-slate-400">
          {configured ? (
            <>
              <Badge
                variant="outline"
                className={`mr-1 text-xs ${PROVIDER_COLORS[currentChain[0].provider] ?? ""}`}
              >
                {currentChain[0].provider}
              </Badge>
              {primaryDisplay}
              {currentChain.length > 1 && (
                <span className="ml-1 text-slate-500">
                  +{currentChain.length - 1} fallback{currentChain.length > 2 ? "s" : ""}
                </span>
              )}
            </>
          ) : (
            <span className="italic text-slate-500">Default (caller decides)</span>
          )}
        </span>
      </button>

      {expanded && (
        <div className="space-y-2 px-3 pb-3">
          {configured && (
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragEnd={handleDragEnd}
            >
              <SortableContext
                items={currentChain.map((_, i) => `${task}-${i}`)}
                strategy={verticalListSortingStrategy}
              >
                <div className="space-y-1">
                  {currentChain.map((entry, i) => (
                    <SortableChainEntry
                      key={`${task}-${i}`}
                      id={`${task}-${i}`}
                      entry={entry}
                      models={models}
                      availableProviders={availableProviders}
                      onRemove={() => handleRemove(i)}
                    />
                  ))}
                </div>
              </SortableContext>
            </DndContext>
          )}

          <div className="flex items-center gap-2">
            {availableModels.length > 0 && (
              <div className="relative">
                <AddModelDropdown
                  models={availableModels}
                  availableProviders={availableProviders}
                  onSelect={handleAdd}
                />
              </div>
            )}
            {configured && (
              <Button
                size="xs"
                variant="outline"
                onClick={onDelete}
                className="text-xs text-red-400 hover:text-red-300"
              >
                Reset to default
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Main export
export default function TaskRoutingConfig() {
  const queryClient = useQueryClient();

  const { data: modelsData } = useQuery({
    queryKey: ["llm-models"],
    queryFn: getLlmModels,
  });

  const { data: routesData } = useQuery({
    queryKey: ["llm-task-routes"],
    queryFn: getLlmTaskRoutes,
  });

  const saveMutation = useMutation({
    mutationFn: ({ task, chain }: { task: string; chain: LlmRouteEntry[] }) =>
      setLlmTaskRoute(task, chain),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["llm-task-routes"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (task: string) => deleteLlmTaskRoute(task),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["llm-task-routes"] }),
  });

  if (!modelsData || !routesData) {
    return (
      <div className="py-4 text-center text-sm text-slate-400">Loading routing config...</div>
    );
  }

  const { models, available_providers } = modelsData;
  const tasks = routesData.tasks;
  const routes = routesData.task_routes;

  return (
    <div className="divide-y divide-slate-800/40">
      {tasks.map((task) => {
        const config = routes[task];
        const chain = config?.chain ?? null;
        return (
          <TaskRow
            key={task}
            task={task}
            chain={chain}
            models={models}
            availableProviders={available_providers}
            onSave={(newChain) => saveMutation.mutate({ task, chain: newChain })}
            onDelete={() => deleteMutation.mutate(task)}
          />
        );
      })}
    </div>
  );
}
