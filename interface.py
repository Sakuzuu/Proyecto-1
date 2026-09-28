"""Initial Tkinter interface for StudyFlow."""
import tkinter as tk
from database import initialize_database

def launch_app() -> None:
    initialize_database()
    root = tk.Tk()
    root.title("StudyFlow")
    root.geometry("720x420")
    root.minsize(600, 350)
    tk.Label(root, text="StudyFlow", font=("Arial", 24, "bold")).pack(pady=(45, 10))
    tk.Label(root, text="Gestión y análisis académico", font=("Arial", 12)).pack(pady=(0, 30))
    tk.Label(root, text="Estructura base inicializada correctamente.", font=("Arial", 11)).pack(pady=10)
    tk.Button(root, text="Cerrar", command=root.destroy, width=14).pack(pady=25)
    root.mainloop()
