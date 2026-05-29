import {
  closestCenter,
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Plus, Trash2 } from "lucide-react";
import type { DraftStep } from "@/lib/draft-types";
import { cn } from "@/lib/utils";

type Props = {
  steps: DraftStep[];
  selectedIndex: number | null;
  onSelect: (index: number) => void;
  onAdd: () => void;
  onDelete: (index: number) => void;
  onReorder: (fromIndex: number, toIndex: number) => void;
};

export function StepList({
  steps,
  selectedIndex,
  onSelect,
  onAdd,
  onDelete,
  onReorder,
}: Props) {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    onReorder(Number(active.id), Number(over.id));
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-neutral-400">
          Steps ({steps.length})
        </h2>
        <button
          type="button"
          onClick={onAdd}
          className="text-blue-400 hover:text-blue-300 text-sm flex items-center gap-1"
        >
          <Plus size={14} /> 新增
        </button>
      </div>

      {steps.length === 0 ? (
        <div className="text-xs text-neutral-500 italic px-2 py-3">
          尚無步驟，點上方新增。
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={steps.map((_, i) => String(i))}
            strategy={verticalListSortingStrategy}
          >
            <ul className="space-y-1">
              {steps.map((step, i) => (
                <SortableStepItem
                  key={`${step.fileLabel}-${i}`}
                  id={String(i)}
                  index={i}
                  step={step}
                  selected={selectedIndex === i}
                  onSelect={onSelect}
                  onDelete={onDelete}
                />
              ))}
            </ul>
          </SortableContext>
        </DndContext>
      )}
    </div>
  );
}

function SortableStepItem({
  id,
  index,
  step,
  selected,
  onSelect,
  onDelete,
}: {
  id: string;
  index: number;
  step: DraftStep;
  selected: boolean;
  onSelect: (index: number) => void;
  onDelete: (index: number) => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <li
      ref={setNodeRef}
      style={style}
      className={cn(
        "flex items-center gap-2 px-3 py-2 rounded cursor-pointer transition-colors",
        selected
          ? "bg-blue-600/20 border border-blue-500/40"
          : "bg-neutral-900 border border-transparent hover:bg-neutral-800",
        isDragging && "opacity-60",
      )}
      onClick={() => onSelect(index)}
    >
      <button
        type="button"
        className="text-neutral-600 hover:text-neutral-300 cursor-grab active:cursor-grabbing p-0.5"
        aria-label="拖曳排序"
        {...attributes}
        {...listeners}
      >
        <GripVertical size={14} />
      </button>
      <span className="text-xs text-neutral-500 w-6 shrink-0">{index + 1}.</span>
      <span className="flex-1 truncate text-sm">
        {step.label || <span className="text-neutral-500">(未命名)</span>}
      </span>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          if (confirm(`刪除步驟「${step.label}」？`)) onDelete(index);
        }}
        className="text-neutral-500 hover:text-red-400 p-1"
        aria-label="刪除步驟"
      >
        <Trash2 size={14} />
      </button>
    </li>
  );
}
