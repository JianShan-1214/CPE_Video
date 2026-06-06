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
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="eyebrow">Steps · {steps.length}</span>
        <button
          type="button"
          onClick={onAdd}
          className="btn btn-quiet text-xs"
        >
          <Plus size={14} /> 新增
        </button>
      </div>

      {steps.length === 0 ? (
        <button
          type="button"
          onClick={onAdd}
          className="w-full rounded-xl border border-dashed border-line px-3 py-6 text-center text-xs text-faint transition-colors hover:border-accent hover:text-accent"
        >
          尚無步驟，點此新增。
        </button>
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
        "group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer border transition-colors",
        selected
          ? "border-accent bg-accent-soft"
          : "border-transparent bg-ink-900 hover:bg-ink-850 hover:border-line",
        isDragging && "opacity-60",
      )}
      onClick={() => onSelect(index)}
    >
      <button
        type="button"
        className="text-faint hover:text-mist cursor-grab active:cursor-grabbing p-0.5"
        aria-label="拖曳排序"
        {...attributes}
        {...listeners}
      >
        <GripVertical size={14} />
      </button>
      <span
        className={cn(
          "meta-mono w-6 shrink-0 text-xs",
          selected ? "text-accent" : "text-faint",
        )}
      >
        {String(index + 1).padStart(2, "0")}
      </span>
      <span
        className={cn(
          "flex-1 truncate text-sm transition-colors",
          selected ? "text-paper" : "text-mist group-hover:text-paper",
        )}
      >
        {step.label || <span className="text-faint">(未命名)</span>}
      </span>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          if (confirm(`刪除步驟「${step.label}」？`)) onDelete(index);
        }}
        className="text-faint hover:text-danger p-1"
        aria-label="刪除步驟"
      >
        <Trash2 size={14} />
      </button>
    </li>
  );
}
