
### Files Modified

| File Path | Modification Made |
| :--- | :--- |
| **`CTFd/models/__init__.py`** | Added `value = db.Column(db.Integer)` to the **`Solves`** class so Python recognizes the new column. |
| **`CTFd/plugins/challenges/__init__.py`** | Updated the `solve` method to include `value=challenge.value` when creating a new `Solves` object. |
| **`CTFd/plugins/dynamic_challenges/__init__.py`** | Updated the `solve` method to call the parent logic *before* recalculating the new (lower) decay value. |
| **`CTFd/utils/scores/__init__.py`** | Changed the scoreboard calculation from `db.func.sum(Challenges.value)` to `db.func.sum(Solves.value)`. |

---
# Special Cases: 
### Non-File Modifications
*   **Database Schema:** You manually executed a SQL command (`ALTER TABLE solves ADD COLUMN value INT;`) to create the physical storage for the points.
*   **System State:** A container restart (`docker compose restart`) was required to reload the Python environment and apply the code changes.



