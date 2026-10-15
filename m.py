# gnome-terminal -- bash -c 'watch -n 1 nvidia-smi; exec bash' & \
# gnome-terminal -- bash -c 'watch -n 1 '\''nvidia-smi -q -d PERFORMANCE | grep -iE "thermal|power|slowdown|clocks event"'\''; exec bash' & \
# gnome-terminal -- bash -c 'watch -n 1 '\''nvidia-smi --query-gpu=temperature.gpu,clocks.sm,clocks.max.sm,power.draw --format=csv'\''; exec bash' &
# les trois process à lancer

# étape 1 : lancer ces 3 process
# étape 2 : récupérer la sortie et parser les informations necessaires
# étape 3 : afficher avec tkinter à l'écran dans une fenetre dédiée

# Informations à récupérer avec le parser : Temp GPU/Max temp, Frequence/max freq, Puissance W/Max W, VRAM/ MAX VRAM, tous les clock events, Perf P8 de nvidia-smi, les processes recup par Nvidia smi


from sys import stdout
import subprocess, re, setproctitle
import tkinter as tk
from tkinter import ttk






# Mettre les commandes en string et renvoyer un tableau
def set_cmd():
    # Consommation GPU globale
    cmd1 = ["nvidia-smi"]

    # Événements de limitation des fréquences GPU
    cmd2 = [
        "bash", "-c",
        'nvidia-smi -q -d PERFORMANCE | grep -iE "thermal|power|slowdown|clocks event"'
    ]

    #  Température, fréquence GPU et puissance
    cmd3 = [
        "nvidia-smi",
        "--query-gpu=temperature.gpu,clocks.sm,clocks.max.sm,power.draw",
        "--format=csv"
    ]

    # RAM système (total / utilisée, en MiB) - LC_ALL=C force les libellés en anglais
    cmd4 = ["bash", "-c", "LC_ALL=C free -m"]

    # RAM de chaque processus (PID et RSS en KiB, sans l'en-tête grâce aux "=")
    cmd5 = ["ps", "-eo", "pid=,rss="]

    return [cmd1, cmd2, cmd3, cmd4, cmd5]





# Lancer les commandes reçues avec subprocess et les contenir dans une variable à parser
def run_subprocesses(commands):
    results = []

    for cmd in commands:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True
        )
        results.append(result.stdout)

    return results



# parser l'output pour recuperer des data => code de la fonction écrit par Claude.
def parser(result):
    print("PARSER ==> APPELLER")
    print(result)

    # result[0] = nvidia-smi
    # result[1] = événements d'horloge
    # result[2] = température / fréquences / puissance
    # result[3] = RAM système
    # result[4] = RAM par processus

    data = {
        "temperature": None,
        "temperature_max": None,
        "frequency": None,
        "frequency_max": None,
        "power": None,
        "power_max": None,
        "vram_used": None,
        "vram_total": None,
        "ram_used": None,
        "ram_total": None,
        "clock_events": {},
        "clock_event_counters": {},
        "performance_state": None,
        "processes": []
    }

    # --------------------------------------------------
    # 1. Analyse de nvidia-smi (result[0])
    # --------------------------------------------------
    if len(result) > 0:
        output = result[0]

        # Température, état P0/P8, puissance
        match = re.search(
            r"\|\s*N/A\s+(\d+)C\s+(P\d+)\s+"
            r"(\d+)W\s*/\s*(\d+)W\s+\|\s*"
            r"(\d+)MiB\s*/\s*(\d+)MiB",
            output
        )

        if match:
            data["temperature"] = int(match.group(1))
            data["performance_state"] = match.group(2)
            data["power"] = int(match.group(3))
            data["power_max"] = int(match.group(4))
            data["vram_used"] = int(match.group(5))
            data["vram_total"] = int(match.group(6))

        # Processus GPU : prend en charge C, G et C+G
        process_pattern = re.compile(
            r"^\|\s*(\d+)\s+N/A\s+N/A\s+"
            r"(\d+)\s+([A-Z+]+)\s+(.+?)\s+(\d+)\s*MiB\s*\|$",
            re.MULTILINE
        )

        for match in process_pattern.finditer(output):
            data["processes"].append({
                "gpu": int(match.group(1)),
                "pid": int(match.group(2)),
                "type": match.group(3),
                "name": match.group(4).strip(),
                "vram": int(match.group(5))
            })

    # --------------------------------------------------
    # 2. Événements d'horloge (result[1])
    # --------------------------------------------------
    if len(result) > 1:
        output = result[1]

        # Événements actifs / inactifs
        event_section = output.split(
            "Clocks Event Reasons Counters"
        )[0]

        for line in event_section.splitlines():
            match = re.match(
                r"\s*(.+?)\s*:\s*(Active|Not Active)\s*$",
                line
            )

            if match:
                name = match.group(1).strip()
                data["clock_events"][name] = (
                    match.group(2) == "Active"
                )

        # Compteurs cumulés en microsecondes
        counter_section = output.split(
            "Clocks Event Reasons Counters"
        )

        if len(counter_section) > 1:
            for line in counter_section[1].splitlines():
                match = re.match(
                    r"\s*(.+?)\s*:\s*(\d+)\s*us\s*$",
                    line
                )

                if match:
                    data["clock_event_counters"][
                        match.group(1).strip()
                    ] = int(match.group(2))

    # --------------------------------------------------
    # 3. Température, fréquences et puissance (result[2])
    # --------------------------------------------------
    if len(result) > 2:
        output = result[2]

        match = re.search(
            r"(?m)^(\d+),\s*(\d+)\s*MHz,\s*"
            r"(\d+)\s*MHz,\s*([\d.]+)\s*W",
            output
        )

        if match:
            data["temperature"] = int(match.group(1))
            data["frequency"] = int(match.group(2))
            data["frequency_max"] = int(match.group(3))
            data["power"] = float(match.group(4))
    
     # --------------------------------------------------
    # 4. RAM système (result[3])
    # --------------------------------------------------
    if len(result) > 3:
        output = result[3]

        # Ligne "Mem:" -> total, utilisée (en MiB)
        match = re.search(
            r"(?m)^Mem:\s+(\d+)\s+(\d+)",
            output
        )

        if match:
            data["ram_total"] = int(match.group(1))
            data["ram_used"] = int(match.group(2))

    # --------------------------------------------------
    # 5. RAM par processus (result[4])
    # --------------------------------------------------
    if len(result) > 4:
        output = result[4]

        # PID -> RAM résidente en MiB (ps donne des KiB)
        ram_by_pid = {}

        for match in re.finditer(
            r"(?m)^\s*(\d+)\s+(\d+)\s*$",
            output
        ):
            ram_by_pid[int(match.group(1))] = int(match.group(2)) // 1024

        # Associe la RAM aux processus GPU trouvés dans la section 1
        for process in data["processes"]:
            if process["pid"] in ram_by_pid:
                process["ram"] = ram_by_pid[process["pid"]]

    print("\n")
    print("\n")
    print("\n")
    print("DATA PARSER : ", data)

    return data



# afficher les data récupérer dans une interface graphique ==> code de la fonction écrite par Claude.
def render():
    root = tk.Tk()
    root.title("GPU MONITOR PERSO")
    root.geometry("1000x720")
    root.minsize(800, 600)
    root.configure(bg="#111827")

    BG = "#111827"
    PANEL = "#1f2937"
    FG = "#f9fafb"
    MUTED = "#9ca3af"
    GREEN = "#34d399"
    BLUE = "#60a5fa"
    ORANGE = "#fb923c"
    RED = "#f87171"

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(
        "Treeview",
        background=PANEL,
        foreground=FG,
        fieldbackground=PANEL,
        rowheight=28,
        borderwidth=0
    )
    style.configure(
        "Treeview.Heading",
        background="#374151",
        foreground=FG,
        font=("Arial", 10, "bold")
    )

    # --------------------------------------------------
    # En-tête
    # --------------------------------------------------
    header = tk.Frame(root, bg=BG)
    header.pack(fill="x", padx=20, pady=(15, 5))

    tk.Label(
        header,
        text="GPU MONITOR",
        font=("Arial", 22, "bold"),
        fg=FG,
        bg=BG
    ).pack(side="left")

    status_var = tk.StringVar(value="Initialisation...")
    tk.Label(
        header,
        textvariable=status_var,
        font=("Arial", 10),
        fg=GREEN,
        bg=BG
    ).pack(side="right")

    # --------------------------------------------------
    # Cartes de métriques
    # --------------------------------------------------
    metrics_frame = tk.Frame(root, bg=BG)
    metrics_frame.pack(fill="x", padx=15, pady=10)

    metrics = {}

    cards = [
        ("Température", "temperature", "°C", GREEN),
        ("Fréquence GPU", "frequency", "MHz", BLUE),
        ("Puissance", "power", "W", ORANGE),
        ("VRAM utilisée", "vram_used", "MiB", RED),
        ("RAM utilisée", "ram_used", "MiB", GREEN),
        ("État GPU", "performance_state", "", BLUE),
        ("Fréquence max", "frequency_max", "MHz", BLUE),
        ("Puissance max", "power_max", "W", ORANGE),
        ("VRAM totale", "vram_total", "MiB", RED),
        ("RAM totale", "ram_total", "MiB", GREEN),
    ]

    for index, (title, key, unit, color) in enumerate(cards):
        card = tk.Frame(
            metrics_frame,
            bg=PANEL,
            padx=12,
            pady=12,
            highlightthickness=1,
            highlightbackground="#374151"
        )

        card.grid(
            row=index // 5,
            column=index % 5,
            sticky="nsew",
            padx=5,
            pady=5
        )

        tk.Label(
            card,
            text=title,
            font=("Arial", 10),
            fg=MUTED,
            bg=PANEL
        ).pack(anchor="w")

        value_var = tk.StringVar(value="N/D")
        metrics[key] = (value_var, unit)

        tk.Label(
            card,
            textvariable=value_var,
            font=("Arial", 19, "bold"),
            fg=color,
            bg=PANEL
        ).pack(anchor="w", pady=(8, 0))

    for col in range(5):
        metrics_frame.columnconfigure(col, weight=1)

    # --------------------------------------------------
    # Événements GPU
    # --------------------------------------------------
    events_frame = tk.LabelFrame(
        root,
        text="  Clock events et compteurs  ",
        font=("Arial", 11, "bold"),
        fg=FG,
        bg=PANEL,
        padx=10,
        pady=10
    )
    events_frame.pack(
        fill="both",
        expand=True,
        padx=20,
        pady=8
    )

    events_text = tk.Text(
        events_frame,
        height=8,
        bg=PANEL,
        fg=FG,
        insertbackground=FG,
        font=("Consolas", 10),
        relief="flat",
        wrap="word"
    )
    events_text.pack(fill="both", expand=True)

    # --------------------------------------------------
    # Processus GPU
    # --------------------------------------------------
    processes_frame = tk.LabelFrame(
        root,
        text="  Processus utilisant le GPU  ",
        font=("Arial", 11, "bold"),
        fg=FG,
        bg=PANEL,
        padx=10,
        pady=10
    )
    processes_frame.pack(
        fill="both",
        expand=True,
        padx=20,
        pady=8
    )

    columns = ("gpu", "pid", "type", "name", "vram", "ram")

    tree = ttk.Treeview(
        processes_frame,
        columns=columns,
        show="headings",
        height=5
    )

    headings = {
        "gpu": "GPU",
        "pid": "PID",
        "type": "Type",
        "name": "Processus",
        "vram": "VRAM (MiB)",
        "ram": "RAM (MiB)"
    }

    widths = {
        "gpu": 50,
        "pid": 90,
        "type": 70,
        "name": 330,
        "vram": 110,
        "ram": 110
    }

    for col in columns:
        tree.heading(col, text=headings[col])
        tree.column(col, width=widths[col], anchor="w")

    tree.pack(fill="both", expand=True)

    # --------------------------------------------------
    # Barre de statut
    # --------------------------------------------------
    footer_var = tk.StringVar(value="En attente des données GPU")

    tk.Label(
        root,
        textvariable=footer_var,
        bg=BG,
        fg=MUTED,
        font=("Arial", 9)
    ).pack(anchor="w", padx=20, pady=(2, 12))

    # --------------------------------------------------
    # Mise à jour de l'interface
    # --------------------------------------------------
    def update_display(data):
        for key, (variable, unit) in metrics.items():
            value = data.get(key)

            if value is None:
                display = "N/D"
            else:
                display = f"{value} {unit}".strip()

            variable.set(display)

        # Couleur de la température
        temp = data.get("temperature")

        if temp is not None:
            temp_color = (
                RED if temp >= 85
                else ORANGE if temp >= 70
                else GREEN
            )
            # Le texte de température se trouve dans la 1re carte.
            metrics["temperature"][0].set(f"{temp} °C")

        # Événements actifs et compteurs
        events_text.configure(state="normal")
        events_text.delete("1.0", "end")

        events = data.get("clock_events", {})
        counters = data.get("clock_event_counters", {})

        if events:
            for name, active in events.items():
                state = "ACTIF" if active else "Inactif"
                events_text.insert(
                    "end",
                    f"{name:<48} {state}\n"
                )
        else:
            events_text.insert(
                "end",
                "Aucun événement détecté ou donnée indisponible.\n"
            )

        if counters:
            events_text.insert("end", "\nCompteurs cumulés :\n")

            for name, value in counters.items():
                events_text.insert(
                    "end",
                    f"{name:<48} {value} µs\n"
                )

        events_text.configure(state="disabled")

        # Processus
        for item in tree.get_children():
            tree.delete(item)

        for process in data.get("processes", []):
            tree.insert(
                "",
                "end",
                values=(
                    process.get("gpu", ""),
                    process.get("pid", ""),
                    process.get("type", ""),
                    process.get("name", ""),
                    process.get("vram", ""),
                    process.get("ram", "N/D")
                )
            )

        status_var.set("● GPU connecté")
        footer_var.set(
            f"Actualisation automatique toutes les secondes"
            f" | État de performance : "
            f"{data.get('performance_state') or 'N/D'}"
        )

    # --------------------------------------------------
    # Récupération périodique des données
    # --------------------------------------------------
    def refresh():
        try:
            results = run_subprocesses(set_cmd())
            data = parser(results)
            update_display(data)

        except Exception as error:
            status_var.set("● Erreur")
            footer_var.set(str(error))

        finally:
            if root.winfo_exists():
                root.after(1000, refresh)

    root.after(100, refresh)
    root.mainloop()



# Lancer le script
def RUN():
    print("RUN ==> APPELLER RUN SUBPROCESS ET SET CMD")

    render()


setproctitle.setproctitle("GPU_MONITOR_PERSO")
RUN()

