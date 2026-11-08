import heapq
import math
import random
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="MASAR | Smart Building Analytics", page_icon="🏢", layout="wide")

ROOMS = {
    "Classroom 01": {"center": (210, 175), "door": (202, 275), "side": "top"},
    "Classroom 02": {"center": (520, 175), "door": (492, 275), "side": "top"},
    "Classroom 03": {"center": (865, 175), "door": (847, 275), "side": "top"},
    "Classroom 04": {"center": (425, 550), "door": (372, 420), "side": "bottom"},
    "Computer Lab": {"center": (735, 550), "door": (722, 420), "side": "bottom"},
    "Staircase": {"center": (160, 550), "door": (170, 420), "side": "bottom"},
    "Main Entrance": {"center": (60, 350), "door": (60, 350), "side": "corridor"},
}

# This first navigation model represents the main corridor as a walkable grid.
# Room interiors use schematic connectors; Classroom 02 includes a partial
# illustrated furniture-avoidance route, not full collision-free navigation.
CELL = 10
CORRIDOR_X = (60, 1040)
CORRIDOR_Y = (290, 400)


def grid_point(x, y):
    return (round((x - 60) / CELL), round((y - 290) / CELL))


def world_point(node):
    return (60 + node[0] * CELL, 290 + node[1] * CELL)


def astar(start, goal):
    max_x = (CORRIDOR_X[1] - 60) // CELL
    max_y = (CORRIDOR_Y[1] - 290) // CELL
    frontier = [(0, start)]
    came_from = {start: None}
    cost_so_far = {start: 0}
    while frontier:
        _, current = heapq.heappop(frontier)
        if current == goal:
            break
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (current[0] + dx, current[1] + dy)
            if not (0 <= nxt[0] <= max_x and 0 <= nxt[1] <= max_y):
                continue
            new_cost = cost_so_far[current] + 1
            if nxt not in cost_so_far or new_cost < cost_so_far[nxt]:
                cost_so_far[nxt] = new_cost
                priority = new_cost + abs(goal[0] - nxt[0]) + abs(goal[1] - nxt[1])
                heapq.heappush(frontier, (priority, nxt))
                came_from[nxt] = current
    if goal not in came_from:
        return []
    result = []
    node = goal
    while node is not None:
        result.append(world_point(node))
        node = came_from[node]
    return list(reversed(result))


def connector(room, design="Original"):
    # Proposed design: relocate Classroom 02 door farther right.
    # Only the architectural doorway changes; population and behavior stay fixed.
    data = ROOMS[room]
    door_positions = {"Original": 492, "Alternative A": 552,
                      "Alternative B": 582, "Proposed": 612}
    dx, dy = (door_positions.get(design, 492), 275) if room == "Classroom 02" else data["door"]
    if data["side"] == "top":
        return [(dx, dy), (dx, 290), (dx, 320)]
    if data["side"] == "bottom":
        return [(dx, dy), (dx, 400), (dx, 370)]
    return [(60, 350)]


def room_interior_path(room, design="Original"):
    """Illustrative furniture-avoiding connector for Classroom 02.

    Desk rectangles occupy x=420..485 and 545..610 at y=135..162
    and 195..222. The central aisle x=520 and the rear aisle y=245
    avoid these footprints. These are drawing units, not measured metres.
    """
    center = ROOMS[room]["center"]
    door = connector(room, design)[0]
    if room == "Classroom 02":
        return [center, (520, 245), (door[0], 245), door]
    return [center, door]


def complete_room_connector(room, design="Original"):
    interior = room_interior_path(room, design)
    exterior = connector(room, design)
    return interior + exterior[1:]


def calculate_route(origin, destination, design="Original"):
    start = connector(origin, design)
    end = connector(destination, design)
    mid = astar(grid_point(*start[-1]), grid_point(*end[-1]))
    if not mid:
        return []
    # Connect the room marker to its doorway and then into the corridor.
    return complete_room_connector(origin, design) + mid + list(reversed(complete_room_connector(destination, design)))


def create_pedestrians(count, design="Original"):
    """Reproducible route-based animation scenarios (no collision physics yet)."""
    rng = random.Random(2026)
    locations = ["Classroom 01", "Classroom 02", "Classroom 03",
                 "Classroom 04", "Computer Lab", "Staircase"]
    agents = []
    for i in range(count):
        origin = locations[i % len(locations)]
        destination = rng.choice([x for x in locations if x != origin])
        route = calculate_route(origin, destination, design)
        if not route:
            continue
        distance = sum(math.dist(a, b) for a, b in zip(route, route[1:]))
        agents.append({"route": route, "delay": rng.uniform(0, 5),
                       "duration": max(2, distance / rng.uniform(65, 85)),
                       "color": "#E56B3F" if i % 2 else "#2478B7"})
    return agents


def interaction_route(origin, destination, design, lane):
    """Separate opposing corridor flows into illustrative walking lanes.

    Room-to-door connectors remain simplified and are not collision-validated.
    The corridor is a 2D open space; this is not a calibrated crowd model.
    """
    start = connector(origin, design)
    end = connector(destination, design)
    sx, sy = start[-1]
    ex, ey = end[-1]
    # Only corridor geometry is used for the horizontal walking segment.
    # Opposing flows use different lane bands; three lanes per direction.
    travel_right = ex >= sx
    lane_y = (312, 330, 348)[lane % 3] if travel_right else (362, 380, 398)[lane % 3]
    origin_inside = complete_room_connector(origin, design)[:-1]
    destination_inside = complete_room_connector(destination, design)[:-1]
    return (origin_inside + [(sx, lane_y), (ex, lane_y)] +
            list(reversed(destination_inside)))


def build_interaction_simulation(count, time_step=0.25, total_seconds=60, design="Original"):
    """Prototype pedestrian simulation with deterministic door admission.

    Each classroom doorway has a simplified single-file entry queue. A doorway is occupied
    while an agent traverses the short door connector; waiting agents are
    admitted in order. Corridor following uses separate direction lanes and
    minimum-distance yielding. Distances are illustrative, not metres.
    """
    agents = create_pedestrians(count, design)
    rng = random.Random(1701)
    locations = ["Classroom 01", "Classroom 02", "Classroom 03",
                 "Classroom 04", "Computer Lab", "Staircase"]
    state = []
    for i, agent in enumerate(agents):
        origin = locations[i % len(locations)]
        destination = next(name for name, data in ROOMS.items()
                           if data["center"] == agent["route"][-1])
        route = interaction_route(origin, destination, design, i // 2)
        points = [route[0]]
        for a, b in zip(route, route[1:]):
            length = math.dist(a, b)
            steps = max(1, math.ceil(length / 3))
            points.extend((a[0] + (b[0] - a[0]) * j / steps,
                           a[1] + (b[1] - a[1]) * j / steps)
                          for j in range(1, steps + 1))
        state.append({"points": points, "index": 0,
                      "delay": i * 0.42 + rng.uniform(0, 0.12),
                      "speed": rng.uniform(52, 72),
                      "history": [], "wait_steps": 0, "arrival_time": None,
                      "blocked_by": {}, "last_progress_time": 0.0,
                      "color": agent["color"], "origin": origin,
                      "destination": destination, "door_wait_steps": 0})

    # Door gates serialize crossing from either direction. We reserve a door
    # for a short crossing window, rather than letting agents face off at its
    # shared coordinate. This is a scheduling abstraction, not physical flow.
    door_busy_until = {name: 0.0 for name in locations}
    door_owner = {name: None for name in locations}
    door_queue = {name: [] for name in locations}
    frames = int(total_seconds / time_step) + 1
    for frame in range(frames):
        t = frame * time_step
        # Release completed reservations.
        for room in locations:
            if t >= door_busy_until[room]:
                door_owner[room] = None
        for idx, person in enumerate(state):
            if t < person["delay"] or person["arrival_time"] is not None:
                continue
            if person["index"] >= len(person["points"]) - 1:
                person["arrival_time"] = t
                continue
            pos = person["points"][person["index"]]
            next_pos = person["points"][min(person["index"] + 1, len(person["points"]) - 1)]
            # Door request when within a 32-unit approach to the doorway.
            needed = None
            for room in (person["origin"], person["destination"]):
                dx, dy = connector(room, design)[0]
                if (math.dist(pos, (dx, dy)) < 33 or
                        math.dist(next_pos, (dx, dy)) < 33):
                    needed = room
                    break
            # The staircase is a shared circulation endpoint, not a modeled
            # single-file classroom doorway. Applying the same timed gate here
            # causes artificial repeated reservations and permanent blocking.
            # Staircase capacity/physical conflicts are NOT modeled in this MVP.
            if needed == "Staircase":
                needed = None
            if needed is not None and idx not in door_queue[needed] and door_owner[needed] != idx:
                door_queue[needed].append(idx)
            if needed is not None:
                if door_owner[needed] is None and door_queue[needed] and door_queue[needed][0] == idx:
                    door_queue[needed].pop(0)
                    door_owner[needed] = idx
                    door_busy_until[needed] = t + 1.5
                if door_owner[needed] != idx:
                    person["wait_steps"] += 1
                    person["door_wait_steps"] += 1
                    continue
            stride = max(1, round(person["speed"] * time_step / 3))
            proposed_index = min(len(person["points"]) - 1, person["index"] + stride)
            accepted = person["index"]
            blocker = None
            for candidate_index in range(proposed_index, person["index"], -1):
                candidate = person["points"][candidate_index]
                obstruction = None
                if 290 <= candidate[1] <= 400:
                    for j, other in enumerate(state):
                        if j == idx or t < other["delay"] or other["arrival_time"] is not None:
                            continue
                        other_pos = other["points"][other["index"]]
                        if not (290 <= other_pos[1] <= 400):
                            continue
                        # A reserved door connector is governed by its gate;
                        # don't apply corridor spacing twice at the doorway.
                        at_door = any(math.dist(candidate, connector(r, design)[0]) < 35
                                      for r in locations)
                        if not at_door and math.dist(candidate, other_pos) < 9:
                            obstruction = j + 1
                            break
                if obstruction is not None:
                    blocker = obstruction
                    continue
                accepted = candidate_index
                break
            if accepted == person["index"]:
                person["wait_steps"] += 1
                if blocker is not None:
                    person["blocked_by"][blocker] = person["blocked_by"].get(blocker, 0) + 1
            else:
                person["index"] = accepted
                person["last_progress_time"] = t
                if accepted == len(person["points"]) - 1:
                    person["arrival_time"] = t
        for person in state:
            person["history"].append(person["points"][person["index"]])
    return state, total_seconds, time_step


def render_interaction_animation(simulation):
    agents, total_seconds, dt = simulation
    # Reuse the existing floor drawing; overlay an SVG animation built from
    # computed discrete-time positions (rather than independent motion paths).
    circles = []
    for agent in agents:
        history = agent["history"]
        # Keep markup reasonably small by sampling every other frame.
        sampled = history[::2]
        if sampled[-1] != history[-1]:
            sampled.append(history[-1])
        xs = ";".join(f"{x:.1f}" for x, _ in sampled)
        ys = ";".join(f"{y:.1f}" for _, y in sampled)
        times = ";".join(f"{i/(len(sampled)-1):.5f}" for i in range(len(sampled)))
        x0, y0 = sampled[0]
        circles.append(f"""<circle cx=\"{x0:.1f}\" cy=\"{y0:.1f}\" r=\"4\" fill=\"{agent['color']}\" stroke=\"white\" stroke-width=\"1.5\">
<animate attributeName=\"cx\" dur=\"{total_seconds}s\" values=\"{xs}\" keyTimes=\"{times}\" calcMode=\"discrete\" fill=\"freeze\"/>
<animate attributeName=\"cy\" dur=\"{total_seconds}s\" values=\"{ys}\" keyTimes=\"{times}\" calcMode=\"discrete\" fill=\"freeze\"/>
</circle>""")
    return "".join(circles)


def analyze_corridor(simulation, zones=10):
    """Occupancy from recorded positions; corridor only, in illustrative units."""
    agents, duration, dt = simulation
    frame_count = min(len(a["history"]) for a in agents)
    counts = [[0] * zones for _ in range(frame_count)]
    for t in range(frame_count):
        for agent in agents:
            x, y = agent["history"][t]
            # Only positions inside the shared corridor count.
            if 60 <= x <= 1040 and 290 <= y <= 400:
                zone = min(zones - 1, int((x - 60) / (980 / zones)))
                counts[t][zone] += 1
    average = [sum(frame[z] for frame in counts) / frame_count for z in range(zones)]
    peak = [max(frame[z] for frame in counts) for z in range(zones)]
    return average, peak, max(map(sum, counts)), frame_count, dt


def render_heatmap(simulation):
    average, peak, _, _, _ = analyze_corridor(simulation)
    maximum = max(average) if average else 0
    overlays = []
    for i, occupancy in enumerate(average):
        # Stronger red = greater mean simultaneous occupancy in this zone.
        opacity = 0 if maximum == 0 else 0.10 + 0.62 * occupancy / maximum
        x = 60 + i * 98
        overlays.append(
            f'<rect x="{x}" y="290" width="98" height="110" '
            f'fill="#E95445" fill-opacity="{opacity:.3f}" />'
        )
        overlays.append(
            f'<text x="{x + 49}" y="394" font-family="Arial" '
            f'font-size="12" font-weight="bold" text-anchor="middle" '
            f'fill="#142B45">{occupancy:.1f}</text>'
        )
    return "".join(overlays)


def render_floor_plan(route=None, animate=False, pedestrians=None, interaction=None, heatmap=None, design="Original"):
    svg = """
    <svg viewBox="0 0 1100 700" width="100%" xmlns="http://www.w3.org/2000/svg">
      <rect width="1100" height="700" fill="#F7F9FC"/>
      <rect x="45" y="45" width="1010" height="600" fill="#FFFFFF" stroke="#142B45" stroke-width="9"/>
      <rect x="54" y="285" width="992" height="125" fill="#F5EBD5"/>
      <rect x="65" y="65" width="290" height="210" fill="#EAF0F6" stroke="#142B45" stroke-width="6"/>
      <rect x="375" y="65" width="290" height="210" fill="#EAF0F6" stroke="#142B45" stroke-width="6"/>
      <rect x="685" y="65" width="360" height="210" fill="#EAF0F6" stroke="#142B45" stroke-width="6"/>
      <rect x="65" y="420" width="190" height="215" fill="#EDF1F5" stroke="#142B45" stroke-width="6"/>
      <rect x="275" y="420" width="300" height="215" fill="#EAF0F6" stroke="#142B45" stroke-width="6"/>
      <rect x="595" y="420" width="280" height="215" fill="#EAF0F6" stroke="#142B45" stroke-width="6"/>
      <rect x="895" y="420" width="150" height="215" fill="#EDF1F5" stroke="#142B45" stroke-width="6"/>
      <g font-family="Arial" text-anchor="middle" fill="#142B45" font-size="15" font-weight="bold">
        <text x="210" y="105">CLASSROOM 01</text><text x="520" y="105">CLASSROOM 02</text>
        <text x="865" y="105">CLASSROOM 03</text><text x="425" y="460">CLASSROOM 04</text>
        <text x="735" y="460">COMPUTER LAB</text><text x="970" y="460">SERVICES</text>
        <text x="160" y="455">STAIRCASE</text>
      </g>
      <g fill="#C7D4E2" stroke="#7890A8" stroke-width="1.5">
        <rect x="110" y="135" width="65" height="27" rx="3"/><rect x="235" y="135" width="65" height="27" rx="3"/>
        <rect x="110" y="195" width="65" height="27" rx="3"/><rect x="235" y="195" width="65" height="27" rx="3"/>
        <rect x="420" y="135" width="65" height="27" rx="3"/><rect x="545" y="135" width="65" height="27" rx="3"/>
        <rect x="420" y="195" width="65" height="27" rx="3"/><rect x="545" y="195" width="65" height="27" rx="3"/>
        <rect x="740" y="140" width="75" height="25" rx="3"/><rect x="900" y="140" width="75" height="25" rx="3"/>
        <rect x="740" y="200" width="75" height="25" rx="3"/><rect x="900" y="200" width="75" height="25" rx="3"/>
        <rect x="320" y="495" width="65" height="27" rx="3"/><rect x="450" y="495" width="65" height="27" rx="3"/>
        <rect x="320" y="560" width="65" height="27" rx="3"/><rect x="450" y="560" width="65" height="27" rx="3"/>
      </g>
      <g fill="#D8E4ED" stroke="#7890A8" stroke-width="1.5">
        <rect x="625" y="500" width="55" height="35" rx="3"/><rect x="695" y="500" width="55" height="35" rx="3"/>
        <rect x="765" y="500" width="55" height="35" rx="3"/><rect x="625" y="565" width="55" height="35" rx="3"/>
        <rect x="695" y="565" width="55" height="35" rx="3"/><rect x="765" y="565" width="55" height="35" rx="3"/>
      </g>
      <g stroke="#7890A8" stroke-width="3">
        <path d="M90 485 H230 M90 505 H230 M90 525 H230 M90 545 H230 M90 565 H230 M90 585 H230"/>
      </g>
      <path d="M160 595 V470 M150 482 L160 470 L170 482" fill="none" stroke="#C49A45" stroke-width="3"/>
      <g stroke-width="12">
        <path d="M180 275 H225" stroke="#EAF0F6"/><path d="M470 275 H515" stroke="#EAF0F6"/>
        <path d="M825 275 H870" stroke="#EAF0F6"/><path d="M350 420 H395" stroke="#EAF0F6"/>
        <path d="M700 420 H745" stroke="#EAF0F6"/><path d="M145 420 H195" stroke="#EDF1F5"/>
      </g>
      <g stroke="#C49A45" stroke-width="2.5" fill="none">
        <path d="M180 275 V230 A45 45 0 0 1 225 275"/><path d="M470 275 V230 A45 45 0 0 1 515 275"/>
        <path d="M825 275 V230 A45 45 0 0 1 870 275"/><path d="M350 420 V465 A45 45 0 0 0 395 420"/>
        <path d="M700 420 V465 A45 45 0 0 0 745 420"/><path d="M145 420 V470 A50 50 0 0 0 195 420"/>
      </g>
      <g font-family="Arial" text-anchor="middle">
        <text x="550" y="335" fill="#142B45" font-size="18" font-weight="bold">MAIN CORRIDOR</text>
        <text x="550" y="360" fill="#8B754D" font-size="12">PEDESTRIAN CIRCULATION ZONE</text>
      </g>
      <path d="M45 325 V375" stroke="#F5EBD5" stroke-width="14"/>
      <path d="M45 325 H95 A50 50 0 0 1 45 375" stroke="#16845B" stroke-width="3" fill="none"/>
      <text x="118" y="395" text-anchor="middle" font-family="Arial" font-size="14" font-weight="bold" fill="#16845B">MAIN ENTRANCE</text>
      <text x="1010" y="35" font-family="Arial" font-size="16" font-weight="bold" fill="#142B45">N ↑</text>
    """
    if design in ("Alternative A", "Alternative B", "Proposed"):
        # Architectural change: close the old Classroom 02 doorway and open
        # a new 45-unit doorway near x=612. The simulation uses the same door.
        new_x = {"Alternative A": 552, "Alternative B": 582, "Proposed": 612}[design]
        svg += f"""
          <path d="M470 275 H515" stroke="#142B45" stroke-width="6"/>
          <path d="M{new_x-22} 275 H{new_x+23}" stroke="#EAF0F6" stroke-width="12"/>
          <path d="M{new_x-22} 275 V230 A45 45 0 0 1 {new_x+23} 275"
                stroke="#C49A45" stroke-width="2.5" fill="none"/>
          <text x="{new_x}" y="250" text-anchor="middle" font-size="10"
                fill="#16845B" font-family="Arial">NEW DOOR</text>
        """
    if route:
        # Render the computed route above the plan, inside the same SVG.
        path_points = " ".join(f"{x:.0f},{y:.0f}" for x, y in route)
        sx, sy = route[0]
        ex, ey = route[-1]
        svg += f'''
          <polyline points="{path_points}" fill="none" stroke="#16845B" stroke-width="6"
                    stroke-linecap="round" stroke-linejoin="round" opacity="0.9"/>
          <circle cx="{sx}" cy="{sy}" r="11" fill="#16845B" stroke="white" stroke-width="3"/>
          <circle cx="{ex}" cy="{ey}" r="11" fill="#C49A45" stroke="white" stroke-width="3"/>
        '''
    if route and animate:
        motion_path = " ".join(
            ("M" if i == 0 else "L") + f"{x:.0f},{y:.0f}"
            for i, (x, y) in enumerate(route)
        )
        svg += f'''
          <circle r="10" fill="#E56B3F" stroke="white" stroke-width="3">
            <animateMotion dur="8s" repeatCount="1" fill="freeze" path="{motion_path}"/>
          </circle>
        '''
    if pedestrians:
        for agent in pedestrians:
            motion_path = " ".join(
                ("M" if i == 0 else "L") + f"{x:.0f},{y:.0f}"
                for i, (x, y) in enumerate(agent["route"])
            )
            delay = agent["delay"]
            duration = agent["duration"]
            color = agent["color"]
            svg += f'''
              <circle r="6" fill="{color}" stroke="white" stroke-width="1.5"
                      visibility="hidden">
                <set attributeName="visibility" to="visible" begin="{delay:.2f}s" fill="freeze"/>
                <animateMotion begin="{delay:.2f}s" dur="{duration:.2f}s"
                               repeatCount="1" fill="freeze" path="{motion_path}"/>
              </circle>
            '''
    if heatmap is not None:
        svg += render_heatmap(heatmap)
    if interaction is not None:
        svg += render_interaction_animation(interaction)
    svg += "</svg>"
    components.html(svg, height=720, scrolling=False)
    st.caption("Illustrative educational floor plan | Prototype geometry (not to scale)")


st.markdown("""
<style>
.block-container {padding-top: 2rem;}
h1, h2, h3 {color: #142B45;}
[data-testid="stMetric"] {background: #F3F6F9; padding: 18px; border-radius: 10px;}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("MASAR")
    st.caption("SMART BUILDING ANALYTICS")
    st.divider()
    page = st.radio("WORKSPACE", ["Dashboard", "Simulation", "Analysis", "Design Comparison", "AI Prediction (Experimental)"])
    st.divider()
    st.success("Prototype Development")

st.title("Building Movement Analysis")
st.caption("Analyze pedestrian circulation. Identify congestion. Improve building design.")
st.divider()

if page == "Dashboard":
    st.subheader("Project Overview")
    c1, c2, c3 = st.columns(3)
    c1.metric("Building Type", "Educational")
    c2.metric("Simulation Status", "Not Started")
    c3.metric("Analysis Status", "Pending")
    st.divider()
    left, right = st.columns([1.5, 1])
    with left:
        with st.container(border=True):
            st.subheader("Floor Plan Workspace")
            st.caption("EDUCATIONAL BUILDING | FLOOR 01")
            render_floor_plan()
    with right:
        with st.container(border=True):
            st.subheader("Quick Scenario Setup")
            students = st.slider("Number of Pedestrians", 10, 200, 60, 10)
            duration = st.slider("Simulation Duration (seconds)", 30, 300, 120, 30)
            if st.button("Prepare Simulation"):
                st.session_state["students"] = students
                st.session_state["duration"] = duration
                st.success("Scenario settings saved.")
    st.divider()
    st.subheader("Core Analysis Capabilities")
    a, b, c = st.columns(3)
    a.markdown("01 | Movement Tracking")
    a.caption("Visualize pedestrian routes.")
    b.markdown("02 | Density Analysis")
    b.caption("Identify high-density areas.")
    c.markdown("03 | Design Evaluation")
    c.caption("Compare alternative layouts.")

elif page == "Simulation":
    st.subheader("Pedestrian Route Finder")
    st.caption("Step 1: A* route planning on a simplified corridor navigation grid.")
    left, right = st.columns([1.5, 1])
    with right:
        with st.container(border=True):
            st.markdown("**Choose movement scenario**")
            origin = st.selectbox("Starting point", list(ROOMS), index=0)
            destinations = [name for name in ROOMS if name != origin]
            destination = st.selectbox("Destination", destinations, index=destinations.index("Computer Lab") if "Computer Lab" in destinations else 0)
            if st.button("Calculate Route", type="primary"):
                st.session_state["route"] = calculate_route(origin, destination)
                st.session_state["route_selection"] = (origin, destination)
                st.session_state["play_animation"] = False
            valid_selection = st.session_state.get("route_selection") == (origin, destination)
            if valid_selection and st.session_state.get("route"):
                if st.button("▶ Animate Pedestrian"):
                    st.session_state["play_animation"] = True
            if st.session_state.get("route_selection") != (origin, destination):
                st.info("Click Calculate Route to update the displayed route.")
            elif st.session_state.get("route"):
                st.success(f"Route found: {origin} → {destination}")
                st.caption("Green = start and route | Gold = destination")
            else:
                st.warning("No valid route found.")
            st.info("Prototype: corridor navigation only. Room interiors and furniture are not yet modeled as walkable geometry.")
    with left:
        with st.container(border=True):
            st.subheader("Navigation Workspace")
            selection = st.session_state.get("route_selection")
            shown_route = st.session_state.get("route") if selection == (origin, destination) else None
            render_floor_plan(
                shown_route,
                animate=bool(shown_route and st.session_state.get("play_animation"))
            )
            if shown_route and st.session_state.get("play_animation"):
                st.caption("Orange marker = one virtual pedestrian moving along the planned route (8 seconds). Reload or calculate again to replay.")

    st.divider()
    st.subheader("Multi-Pedestrian Movement Test")
    st.caption("Independent pedestrians follow computed routes with staggered departures. This is not yet a crowd-interaction or congestion model.")
    n_agents = st.slider("Virtual pedestrians", 3, 30, 12, 3)
    if st.button("▶ Run Group Movement", type="primary"):
        st.session_state["group_agents"] = create_pedestrians(n_agents)
        st.session_state["group_count"] = n_agents
    if st.session_state.get("group_agents"):
        st.success(f"Displaying {st.session_state['group_count']} virtual pedestrians on different routes.")
        with st.container(border=True):
            render_floor_plan(pedestrians=st.session_state["group_agents"])
        st.caption("Blue/orange dots = virtual pedestrians. Departure offsets: 0–5 seconds. Speeds are illustrative SVG units, not validated meters/second. Overlap and collision avoidance are not modeled yet.")

    st.divider()
    st.subheader("Crowd Interaction Test")
    st.caption("Discrete-time movement with a simple minimum-spacing rule in the corridor. Not a validated crowd physics model.")
    interaction_count = st.slider("Pedestrians with interaction", 3, 24, 12, 3)
    if st.button("▶ Run Interaction Test", type="primary"):
        st.session_state["interaction_simulation"] = build_interaction_simulation(interaction_count)
        st.session_state["interaction_count"] = interaction_count
    if st.session_state.get("interaction_simulation"):
        simulation = st.session_state["interaction_simulation"]
        waits = sum(a["wait_steps"] for a in simulation[0])
        st.success(f"Interaction model prepared for {st.session_state['interaction_count']} pedestrians.")
        st.metric("Total yielding time (illustrative)", f"{waits * simulation[2]:.1f} s")
        with st.container(border=True):
            render_floor_plan(interaction=simulation)
        st.caption("Dots pause when another pedestrian is too close in the modeled corridor. Timing and distance are illustrative SVG units; classroom furniture and full body dynamics are not modeled.")

elif page == "Analysis":
    st.subheader("Corridor Occupancy Heatmap")
    st.caption("Recorded virtual-pedestrian positions from the interaction simulation. Fixed scenario seed: 2026.")
    count = st.slider("Pedestrians for heatmap", 3, 24, 12, 3, key="heatmap_count")
    if st.button("Generate Heatmap", type="primary"):
        with st.spinner("Calculating recorded positions..."):
            st.session_state["heatmap_simulation"] = build_interaction_simulation(count)
            st.session_state["heatmap_people"] = count
    simulation = st.session_state.get("heatmap_simulation")
    if simulation:
        avg, peak, maximum, frames, dt = analyze_corridor(simulation)
        a, b, c = st.columns(3)
        a.metric("Pedestrians simulated", st.session_state["heatmap_people"])
        b.metric("Peak corridor occupancy", f"{maximum} people")
        c.metric("Most occupied zone", f"Zone {avg.index(max(avg)) + 1}")
        st.markdown("**Average simultaneous occupancy by corridor zone**")
        st.caption("Darker red = more pedestrians present on average. Numbers on zones are average simultaneous people, not people/m².")
        with st.container(border=True):
            render_floor_plan(heatmap=simulation)
        st.bar_chart({f"Zone {i+1}": value for i, value in enumerate(avg)},
                     x_label="Corridor zone", y_label="Average people")
        st.caption("The corridor is divided into 10 equal SVG-width zones. Values are averaged over all recorded time steps. This is occupancy, NOT physical density: dimensions are not calibrated in meters. The illustrative model is not validated against real pedestrian data.")
        st.info("For a fair design comparison, keep the same population, routes, arrival schedule, and random seed. A calibrated building scale and improved collision handling are required before reporting people/m².")
    else:
        st.info("Choose a pedestrian count and click Generate Heatmap.")

elif page == "AI Prediction (Experimental)":
    st.subheader("AI Congestion Prediction | Experimental surrogate")
    st.caption("Random Forest regression trained on synthetic simulator outputs, not observed building data.")
    st.warning("Research demonstration only. Predictions are not verified congestion forecasts, safety assessments, or design approvals.")
    st.markdown("#### Step 1 — Train and evaluate")
    st.write("Predict cumulative pedestrian waiting (person-seconds) from pedestrian count and Classroom 02 door position. Entire pedestrian counts are held out from training.")
    if st.button("Train and evaluate AI model", type="primary", key="train_ai"):
        try:
            import numpy as np
            from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor, HistGradientBoostingRegressor
            from sklearn.metrics import mean_absolute_error
        except ImportError:
            st.error("Install dependencies: python -m pip install scikit-learn numpy")
        else:
            designs = [("Original", 492), ("Alternative A", 552),
                       ("Alternative B", 582), ("Proposed", 612)]
            # Entire population counts are separated across three partitions.
            training_counts = [10, 12, 15, 18, 20, 22, 26, 28, 32, 34, 37, 40, 43]
            validation_counts = [21, 33, 42]
            test_counts = [24, 30, 39, 45]
            records = []
            with st.spinner("Generating independent synthetic training, validation and test scenarios..."):
                for split, counts in [("Training", training_counts),
                                      ("Validation", validation_counts),
                                      ("Held-out", test_counts)]:
                    for n in counts:
                        for name, door_x in designs:
                            agents, _, dt = build_interaction_simulation(n, design=name)
                            records.append({"Pedestrians": n, "Design": name, "Door x": door_x,
                                "Waiting (person-s)": round(sum(a["wait_steps"] for a in agents) * dt, 2),
                                "Completed": sum(a["arrival_time"] is not None for a in agents),
                                "Split": split})
                train = [r for r in records if r["Split"] == "Training"]
                validation = [r for r in records if r["Split"] == "Validation"]
                test = [r for r in records if r["Split"] == "Held-out"]
                xtrain = np.array([[r["Pedestrians"], r["Door x"]] for r in train])
                ytrain = np.array([r["Waiting (person-s)"] for r in train])
                xval = np.array([[r["Pedestrians"], r["Door x"]] for r in validation])
                yval = np.array([r["Waiting (person-s)"] for r in validation])
                xtest = np.array([[r["Pedestrians"], r["Door x"]] for r in test])
                ytest = np.array([r["Waiting (person-s)"] for r in test])
                candidates = {
                    "Random Forest": RandomForestRegressor(n_estimators=250, max_depth=8, min_samples_leaf=1, random_state=2026),
                    "Extra Trees": ExtraTreesRegressor(n_estimators=250, max_depth=10, random_state=2026),
                    "Gradient Boosting": HistGradientBoostingRegressor(max_iter=150, max_leaf_nodes=7, min_samples_leaf=3, learning_rate=0.06, random_state=2026),
                }
                trained = {}
                validation_errors = {}
                for name, model in candidates.items():
                    model.fit(xtrain, ytrain)
                    trained[name] = model
                    validation_errors[name] = float(mean_absolute_error(yval, model.predict(xval)))
                # Select the algorithm ONLY on validation, never on held-out test.
                best_name = min(validation_errors, key=validation_errors.get)
                best_model = trained[best_name]
                predictions = best_model.predict(xtest)
                evaluations = [{"Method": name,
                                "Validation MAE (person-s)": round(validation_errors[name], 2),
                                "Held-out MAE (person-s)": round(float(mean_absolute_error(ytest, model.predict(xtest))), 2)}
                               for name, model in trained.items()]
                # Simple no-AI baseline uses only training rows.
                baseline_pred = []
                for r in test:
                    nearest = min((t for t in train if t["Design"] == r["Design"]),
                                  key=lambda t: abs(t["Pedestrians"] - r["Pedestrians"]))
                    baseline_pred.append(nearest["Waiting (person-s)"])
                baseline_mae = float(mean_absolute_error(ytest, baseline_pred))
                evaluations.append({"Method": "Nearest-count baseline (no AI)",
                                    "Validation MAE (person-s)": None,
                                    "Held-out MAE (person-s)": round(baseline_mae, 2)})
                st.session_state["masar_ai"] = {
                    "model": best_model, "name": best_name, "records": records,
                    "train_count": len(train), "validation_count": len(validation),
                    "test_count": len(test), "train_min": min(training_counts),
                    "train_max": max(training_counts),
                    "mae": float(mean_absolute_error(ytest, predictions)),
                    "baseline_mae": baseline_mae, "evaluations": evaluations,
                    "test_details": [{"Pedestrians": r["Pedestrians"], "Design": r["Design"],
                        "Actual wait (person-s)": r["Waiting (person-s)"],
                        "AI predicted wait (person-s)": round(float(pred), 2),
                        "Absolute error (person-s)": round(abs(r["Waiting (person-s)"] - float(pred)), 2),
                        "Completed": f'{r["Completed"]}/{r["Pedestrians"]}'}
                        for r, pred in zip(test, predictions)]}
    ai = st.session_state.get("masar_ai")
    if ai:
        st.success("Training complete. Counts 24, 30, 39 and 45 were reserved for final testing and never used to fit or select the model.")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Training scenarios", ai.get("train_count", "N/A"))
        c2.metric("Validation scenarios", ai.get("validation_count", "N/A"))
        c3.metric("Held-out scenarios", ai.get("test_count", "N/A"))
        c4.metric("Held-out model MAE", f'{ai["mae"]:.2f} person-s')
        c5.metric("Baseline MAE", f'{ai["baseline_mae"]:.2f} person-s')
        st.write(f'**Selected experimental model:** {ai["name"]}')
        if ai["mae"] < ai["baseline_mae"]:
            st.info("On this held-out set, the selected ML model beats the nearest-count baseline. This does not establish real-world accuracy.")
        else:
            st.warning("The ML model does not beat the simple baseline on this test. Do not claim improved predictive accuracy.")
        st.caption("The algorithm was chosen using a separate validation set. Held-out results were not used for model selection. All data remain synthetic; real-world validation is still needed.")
        with st.expander("Compare algorithms with the non-AI baseline", expanded=True):
            st.dataframe(ai["evaluations"], hide_index=True, use_container_width=True)
        with st.expander("View held-out predictions"):
            st.dataframe(ai["test_details"], hide_index=True, use_container_width=True)
        st.markdown("#### Step 2 — Predict and verify a scenario")
        n = st.slider("Pedestrians to predict", 10, 45, 30, 1, key="ai_count")
        design = st.selectbox("Doorway candidate", ["Original", "Alternative A", "Alternative B", "Proposed"], key="ai_design")
        door_x = {"Original": 492, "Alternative A": 552, "Alternative B": 582, "Proposed": 612}[design]
        estimate = max(0.0, float(ai["model"].predict([[n, door_x]])[0]))
        st.metric("AI-estimated cumulative waiting", f"{estimate:.1f} person-seconds")
        if n > ai["train_max"] or n < ai["train_min"]:
            st.warning(f"Population {n} is outside the model training range ({ai['train_min']}–{ai['train_max']}). Extrapolation may be unreliable.")
        st.caption("This AI model predicts waiting only. It does not predict journey completion; verify completion separately with the simulator.")
        st.caption("Prediction is an estimate of this synthetic simulator's cumulative waiting, not observed real-world performance.")
        if st.button("Verify against the actual simulator", key="ai_verify"):
            agents, _, dt = build_interaction_simulation(n, design=design)
            actual = sum(a["wait_steps"] for a in agents) * dt
            complete = sum(a["arrival_time"] is not None for a in agents)
            st.session_state["masar_ai_verification"] = {
                "n": n, "design": design, "estimate": estimate,
                "actual": actual, "completed": complete}
        verification = st.session_state.get("masar_ai_verification")
        if verification and verification["n"] == n and verification["design"] == design:
            a, b, c = st.columns(3)
            a.metric("Simulated wait", f'{verification["actual"]:.1f} person-s')
            b.metric("Absolute AI error", f'{abs(verification["actual"] - verification["estimate"]):.1f} person-s')
            c.metric("Completed", f'{verification["completed"]}/{n}')
            if verification["completed"] < n:
                st.warning(f"{n - verification['completed']} of {n} simulated journeys did not finish within 60 seconds. Waiting alone must not be used to rank this design.")
            st.info("The simulator is a synthetic reference, not real-world ground truth. This check is not an independent real-building validation.")
        st.markdown("#### Step 3 — AI-assisted design recommendation")
        st.write("Compare four predefined Classroom 02 doorway positions. The ML model estimates waiting; the simulator separately checks journey completion. This is a decision aid, not autonomous architectural design.")
        if st.button("Recommend best doorway", key="ai_recommend"):
            options = [("Original", 492), ("Alternative A", 552),
                       ("Alternative B", 582), ("Proposed", 612)]
            rows = []
            with st.spinner("Comparing predicted waiting and simulated completion..."):
                for label, x in options:
                    predicted = max(0.0, float(ai["model"].predict([[n, x]])[0]))
                    agents, _, dt = build_interaction_simulation(n, design=label)
                    finished = sum(a["arrival_time"] is not None for a in agents)
                    simulated_wait = sum(a["wait_steps"] for a in agents) * dt
                    rows.append({"Design": label, "Door x": x,
                                 "AI predicted wait (person-s)": round(predicted, 2),
                                 "Simulated wait (person-s)": round(simulated_wait, 2),
                                 "Completed": finished, "Total": n})
            # Prefer complete journeys. If none achieves full completion, prefer
            # the greatest completion count; use simulator wait to break ties.
            winner = min(rows, key=lambda r: (-r["Completed"],
                                               r["Simulated wait (person-s)"],
                                               r["AI predicted wait (person-s)"],
                                               r["Door x"]))
            st.session_state["masar_ai_recommendation"] = {"n": n, "rows": rows, "winner": winner}
        recommendation = st.session_state.get("masar_ai_recommendation")
        if recommendation and recommendation["n"] == n:
            winner = recommendation["winner"]
            st.dataframe(recommendation["rows"], hide_index=True, use_container_width=True)
            st.success(f"Recommended candidate for this synthetic scenario: {winner['Design']} "
                       f"(completed {winner['Completed']}/{n}; simulated waiting "
                       f"{winner['Simulated wait (person-s)']:.2f} person-seconds).")
            if winner["Completed"] < n:
                st.warning("No candidate completed every journey within 60 seconds. "
                           "This is only the least-bad candidate under the stated ranking rules.")
            if n < ai["train_min"] or n > ai["train_max"]:
                st.warning("AI predictions are outside the training population range; interpret cautiously.")
            st.caption("Ranking prioritizes completed journeys, then simulator waiting, then AI-predicted waiting. "
                       "The AI prediction is shown as supporting information, not proof that the layout is optimal. "
                       "Only four predefined door positions were evaluated; desk clearance and engineering feasibility "
                       "require separate validation. Results are synthetic and not real-world performance claims.")
        st.markdown("#### Scope and limitations")
        st.write("This is supervised machine learning on synthetic simulations. It uses only pedestrian count and door position. It does not learn from building sensors, predict physical safety, or validate architectural compliance.")
    else:
        st.info("Click Train and evaluate AI model to generate scenarios and test predictive accuracy.")

elif page == "Design Comparison":
    st.subheader("Design Comparison | Automated Design Insights")
    st.caption("Controlled experiment comparing the original doorway with the selected candidate. Both simulations use identical virtual demand and movement rules; this is exploratory, not engineering validation.")
    count = st.slider("Pedestrians for comparison", 3, 40, 12, 1, key="comparison_count")
    optimization = st.session_state.get("optimization_results")
    candidate = "Alternative A"
    if optimization and optimization.get("count") == count:
        valid = [r for r in optimization["rows"] if r["Geometry check"] == "No illustrated desk intersection"]
        if valid:
            candidate = min(valid, key=lambda r: (-r["Completed"], r["Waiting (person-s)"],
                                                  r["Mean arrival (s)"] if r["Mean arrival (s)"] is not None else float("inf"),
                                                  r["Door x"]))["Design"]
    st.caption(f"Comparison candidate: {candidate}. " +
               ("Selected from the four-candidate evaluation at this pedestrian count." if optimization and optimization.get("count") == count else
                "Default candidate; run Evaluate 4 Doorway Positions below at this count to determine the ranked winner."))
    if st.button("Run Both Designs", type="primary"):
        with st.spinner("Running identical movement scenarios on both layouts..."):
            st.session_state["design_comparison"] = {
                "count": count,
                "Original": build_interaction_simulation(count, design="Original"),
                "candidate": candidate,
                candidate: build_interaction_simulation(count, design=candidate),
            }
    result = st.session_state.get("design_comparison")
    if result:
        compared = result["candidate"]
        st.info(f"Showing {result['count']} pedestrians: Original vs {compared}. Classroom 02 doorway position is the only design variable.")
        metrics = {}
        for design in ("Original", compared):
            sim = result[design]
            agents, duration, dt = sim
            waits = sum(a["wait_steps"] for a in agents) * dt
            completed = [a["arrival_time"] for a in agents if a["arrival_time"] is not None]
            avg, peak, max_occupancy, frames, _ = analyze_corridor(sim)
            metrics[design] = {
                "Total yielding (s)": round(waits, 1),
                "Completed journeys": len(completed),
                "Mean arrival time (s)": round(sum(completed)/len(completed), 1) if completed else None,
                "Peak corridor occupancy": max_occupancy,
            }
        st.markdown("### Animated movement — both designs")
        st.caption("Both animations use the same 60-second simulated window. Opposing flows use separate illustrative corridor lanes. Classroom doors have simplified scheduled access; the staircase is excluded from door gating because its capacity and opposing flows are not yet modeled. Not a validated pedestrian-flow model.")
        left, right = st.columns(2)
        for col, design in ((left, "Original"), (right, compared)):
            with col:
                st.markdown(f"**{design} Design**")
                st.metric("Total yielding time", f"{metrics[design]['Total yielding (s)']:.1f} s")
                st.metric("Journeys completed within 60 s", f"{metrics[design]['Completed journeys']} / {result['count']}")
                st.metric("Peak corridor occupancy", metrics[design]["Peak corridor occupancy"])
                mean_time = metrics[design]["Mean arrival time (s)"]
                st.caption(f"Mean arrival time among completed journeys: {mean_time:.1f} s" if mean_time is not None else "No completed journeys within the simulation window")
                with st.container(border=True):
                    render_floor_plan(interaction=result[design], design=design)
        st.markdown("### Movement diagnostics | Why journeys remain incomplete")
        st.caption("Diagnostic data from the simulation: progress along the computed route, waiting time, and last time each pedestrian moved. This identifies symptoms, not yet a validated collision model.")
        for design in ("Original", compared):
            agents, duration, dt = result[design]
            rows = []
            for i, agent in enumerate(agents, start=1):
                total_segments = max(1, len(agent["points"]) - 1)
                progress = 100 * agent["index"] / total_segments
                blocked_by = agent["blocked_by"]
                main_blocker = max(blocked_by, key=blocked_by.get) if blocked_by else None
                rows.append({
                    "Student": i,
                    "Status": "Arrived" if agent["arrival_time"] is not None else "Incomplete",
                    "Route progress (%)": round(progress, 1),
                    "Waiting (s)": round(agent["wait_steps"] * dt, 1),
                    "Door queue (s)": round(agent["door_wait_steps"] * dt, 1),
                    "Last movement (s)": round(agent["last_progress_time"], 1),
                    "Most frequent blocker": f"Student {main_blocker}" if main_blocker else "None recorded",
                })
            with st.expander(f"{design} — per-student diagnostics", expanded=(design == "Original")):
                st.dataframe(rows, hide_index=True, use_container_width=True)
                unfinished = [r for r in rows if r["Status"] == "Incomplete"]
                stuck = [r for r in unfinished if duration - r["Last movement (s)"] >= 10]
                st.write(f"Incomplete: {len(unfinished)} / {len(rows)} | No progress in final 10 s: {len(stuck)}")
                if stuck:
                    st.warning("At least one student stopped making progress for 10+ simulated seconds. This may indicate unresolved blocking; inspect the movement model and route.")
        st.markdown("### Corridor occupancy heatmaps (average simultaneous people per zone)")
        heat_left, heat_right = st.columns(2)
        for col, design in ((heat_left, "Original"), (heat_right, compared)):
            with col:
                st.markdown(f"**{design} Design**")
                with st.container(border=True):
                    render_floor_plan(heatmap=result[design], design=design)
        st.markdown("### Design Insights | Automated scenario interpretation")
        st.caption("These insights are computed from this run, not generated by a trained AI model. Corridor zones are illustrative, and occupancy is not a calibrated density or a direct measure of congestion.")
        insight_cols = st.columns(2)
        for col, design in zip(insight_cols, ("Original", compared)):
            averages, peaks, _, _, _ = analyze_corridor(result[design])
            hotspot_index = max(range(len(averages)), key=lambda i: averages[i])
            with col:
                st.markdown(f"**{design} | Highest-occupancy zone**")
                st.metric("Corridor zone", f"{hotspot_index + 1} of {len(averages)}")
                st.caption(f"Mean simultaneous occupancy: {averages[hotspot_index]:.2f} people; observed peak in this zone: {peaks[hotspot_index]} people. Zone 1 is nearest the main entrance.")
        o, p = metrics["Original"], metrics[compared]
        wait_change = p["Total yielding (s)"] - o["Total yielding (s)"]
        mean_o, mean_p = o["Mean arrival time (s)"], p["Mean arrival time (s)"]
        complete_equal = o["Completed journeys"] == p["Completed journeys"] == result["count"]
        st.markdown("**Movement efficiency and design trade-off**")
        st.write(f"Completed journeys: {o['Completed journeys']}/{result['count']} Original versus {p['Completed journeys']}/{result['count']} {compared}.")
        if abs(wait_change) < 0.05:
            st.write("Cumulative waiting was effectively unchanged between layouts.")
        else:
            st.write(f"The candidate layout {'reduced' if wait_change < 0 else 'increased'} cumulative waiting by {abs(wait_change):.1f} person-seconds ({abs(wait_change) / o['Total yielding (s)'] * 100:.1f}% relative to original)." if o['Total yielding (s)'] > 0 else "Original waiting was zero; a percentage change is not defined.")
        if mean_o is not None and mean_p is not None:
            mean_change = mean_p - mean_o
            if abs(mean_change) < 0.05:
                st.write("Mean arrival time was effectively unchanged.")
            else:
                st.write(f"Mean arrival time among completed journeys {'increased' if mean_change > 0 else 'decreased'} by {abs(mean_change):.1f} s in the candidate layout.")
        st.markdown("**Evidence-based design recommendation**")
        if not complete_equal:
            st.warning("Do not select a layout from waiting-time figures alone: journey completion differs or some journeys remain incomplete. Review the per-student diagnostics and movement constraints first.")
        elif wait_change < -0.05 and mean_o is not None and mean_p is not None and mean_p > mean_o + 0.05:
            st.info("The relocated doorway reduces modeled waiting but slightly increases mean arrival time. This is a trade-off, not an overall win. Test multiple demand levels and alternative door positions before selecting a design.")
        elif wait_change < -0.05 and mean_o is not None and mean_p is not None and mean_p <= mean_o + 0.05:
            st.success("The candidate doorway is promising in this scenario: it reduces modeled waiting without a meaningful arrival-time penalty. Repeat across scenarios before making a design recommendation.")
        elif wait_change > 0.05:
            st.warning("The candidate doorway increases modeled waiting in this scenario. Retain the original as the reference and investigate alternative doorway locations.")
        else:
            st.info("The layouts show little waiting-time difference in this scenario. More varied scenarios are needed to justify relocating the doorway.")
        st.caption("Confidence: exploratory only. Single deterministic scenario, schematic distances, simplified collision/door rules, and no measured building data. This is decision-support prototyping, not a safety or compliance assessment.")
        if any(metrics[d]["Completed journeys"] < result["count"] for d in ("Original", compared)):
            st.warning("Some journeys did not finish in the simulation window. Waiting-time differences cannot yet be interpreted as proof of improvement; the simplified movement rules may still cause blocking.")
        original_wait = metrics["Original"]["Total yielding (s)"]
        candidate_wait = metrics[compared]["Total yielding (s)"]
        delta = candidate_wait - original_wait
        if delta < -0.05:
            st.info(f"Modeled cumulative yielding was {abs(delta):.1f} seconds lower in the candidate design; check journey completion before interpreting this difference.")
        elif delta > 0.05:
            st.warning(f"The candidate door location increased modeled cumulative yielding by {delta:.1f} seconds in this test.")
        else:
            st.info("The two designs had essentially the same modeled cumulative yielding in this test.")
        st.caption("Interpretation: these are simulation outputs, not observed real-world performance. The model uses uncalibrated SVG distances, simplified room connectors and a 60-second time horizon. A lower total yielding time alone does not establish a better design, especially if fewer journeys complete. Compare completion counts too. Doorway access is scheduled with a simplified queue. It does not prove realistic capacity, safety, or engineering validation.")
    else:
        st.info("Choose a pedestrian count and click Run Both Designs to compare the original and selected candidate.")


    st.divider()
    st.markdown("### Design Optimization | Explore doorway alternatives")
    st.caption("Experimental search over four predefined Classroom 02 doorway positions. "
               "All candidates use the same deterministic pedestrian demand. "
               "Scores are illustrative, not trained AI or engineering validation.")
    st.warning("Prototype route update: Classroom 02 uses a central aisle and a rear aisle to avoid the four illustrated desk rectangles. This is a partial 2D furniture check, not complete building-geometry validation.")
    def connector_crosses_classroom02_furniture(door_x):
        desks = [(420, 485, 135, 162), (545, 610, 135, 162),
                 (420, 485, 195, 222), (545, 610, 195, 222)]
        design = next((name for name, x in (("Original", 492),
                      ("Alternative A", 552), ("Alternative B", 582),
                      ("Proposed", 612)) if x == door_x), "Original")
        route = room_interior_path("Classroom 02", design)
        for (x1, y1), (x2, y2) in zip(route, route[1:]):
            for step in range(1001):
                f = step / 1000
                x, y = x1 + (x2 - x1) * f, y1 + (y2 - y1) * f
                if any(x0 <= x <= x3 and y0 <= y <= y3
                       for x0, x3, y0, y3 in desks):
                    return True
        return False
    if st.button("Evaluate 4 Doorway Positions", key="run_optimization"):
        with st.spinner("Simulating four doorway alternatives..."):
            alternatives = [("Original", 492), ("Alternative A", 552),
                            ("Alternative B", 582), ("Proposed", 612)]
            results = []
            for name, door_x in alternatives:
                sim = build_interaction_simulation(count, design=name)
                agents, _, dt = sim
                completed_times = [a["arrival_time"] for a in agents if a["arrival_time"] is not None]
                _, _, peak, _, _ = analyze_corridor(sim)
                geometry_issue = connector_crosses_classroom02_furniture(door_x)
                results.append({"Design": name, "Door x": door_x,
                                "Geometry check": "Furniture intersection" if geometry_issue else "No illustrated desk intersection",
                                "Completed": len(completed_times),
                                "Waiting (person-s)": round(sum(a["wait_steps"] for a in agents) * dt, 2),
                                "Mean arrival (s)": round(sum(completed_times) / len(completed_times), 2) if completed_times else None,
                                "Peak occupancy": peak})
            st.session_state["optimization_results"] = {"count": count, "rows": results}
    opt = st.session_state.get("optimization_results")
    if opt:
        if opt["count"] != count:
            st.warning(f"Optimization results below use {opt['count']} pedestrians. Rerun to evaluate {count}.")
        rows = opt["rows"]
        st.dataframe(rows, use_container_width=True, hide_index=True)
        valid_rows = [r for r in rows if r["Geometry check"] == "No illustrated desk intersection"]
        if not valid_rows:
            st.error("No candidate passed the preliminary furniture-intersection check. Do not rank these designs.")
            st.stop()
        max_completed = max(r["Completed"] for r in valid_rows)
        eligible = [r for r in valid_rows if r["Completed"] == max_completed]
        # Prioritize completed trips; then minimize cumulative waiting.
        # Mean arrival is a tie-breaker only, and is computed among completers.
        winner = min(eligible, key=lambda r: (r["Waiting (person-s)"],
                                               r["Mean arrival (s)"] if r["Mean arrival (s)"] is not None else float("inf"),
                                               r["Door x"]))
        st.markdown(f"**Best candidate among those passing the preliminary desk check:** {winner['Design']} (door x={winner['Door x']})")
        st.info("To view this candidate in animated comparison, click Run Both Designs above. The selected candidate is updated from this evaluation when the pedestrian count matches.")
        st.caption("Candidates whose illustrated interior connectors intersect desks are excluded. Passing this partial check does not establish collision-free motion, clearance around furniture, or architectural feasibility.")
        st.write(f"Completion: {winner['Completed']}/{opt['count']}; cumulative waiting: "
                 f"{winner['Waiting (person-s)']:.2f} person-seconds; "
                 f"mean arrival: {winner['Mean arrival (s)'] if winner['Mean arrival (s)'] is not None else 'N/A'} s.")
        st.caption("Ranking: first maximize journeys completed within 60 seconds; "
                   "among tied completion counts, minimize cumulative waiting; "
                   "then minimize mean arrival time. This is a transparent rule-based search, "
                   "not a multi-objective optimum or statistically validated result.")
        st.markdown("#### Candidate floor plans")
        a, b = st.columns(2)
        for col, name in ((a, "Alternative A"), (b, "Alternative B")):
            with col:
                st.markdown(f"**{name}**")
                with st.container(border=True):
                    render_floor_plan(design=name)
        st.info("Next validation: repeat at different pedestrian counts, check whether "
                "door locations are geometrically feasible, and verify that ranking remains stable.")
    else:
        st.info("Run the four-candidate evaluation to see a ranked comparison.")

st.divider()
st.caption("MASAR | Smart Building Movement Analysis Platform")
