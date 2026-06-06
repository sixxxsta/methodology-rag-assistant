"use client";

type Props = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Да",
  cancelLabel = "Нет",
  danger = false,
  onConfirm,
  onCancel,
}: Props) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
    >
      <div className="w-full max-w-md rounded-2xl border border-border bg-surface-2 p-6 shadow-xl">
        <h2 id="confirm-title" className="text-lg font-semibold text-text">
          {title}
        </h2>
        <p className="mt-3 text-sm leading-relaxed text-muted">{message}</p>
        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-xl border border-border px-4 py-2 text-sm text-text hover:border-accent"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={
              danger
                ? "rounded-xl bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500"
                : "rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            }
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
