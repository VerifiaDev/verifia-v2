import { ERROR_COPY } from "@/lib/format";
import type { ApiError } from "@/lib/types";

interface Props {
  error: ApiError;
  onRetry: () => void;
  onEdit: () => void;
}

/** Hata: ne oldu → şimdi ne yapabilirsiniz. Teknik ayrıntı kullanıcıya gösterilmez. */
export function ErrorState({ error, onRetry, onEdit }: Props) {
  const copy = ERROR_COPY[error.code] ?? ERROR_COPY.INTERNAL_ERROR;

  return (
    <div className="error-state" role="alert">
      <h2 className="t-h3">{copy.title}</h2>
      <h3 className="t-h4">Ne oldu?</h3>
      <p>{copy.what}</p>
      <h3 className="t-h4">Şimdi ne yapabilirsiniz?</h3>
      <ul className="todo-list">
        {copy.todo.map((t) => (
          <li key={t}>{t}</li>
        ))}
      </ul>
      <div className="actions">
        {copy.retry && (
          <button type="button" className="btn" onClick={onRetry}>
            Yeniden dene
          </button>
        )}
        <button type="button" className={copy.retry ? "btn btn-quiet" : "btn"} onClick={onEdit}>
          İçeriği düzenle
        </button>
      </div>
    </div>
  );
}
