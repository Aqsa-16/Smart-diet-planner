import streamlit as st
import sqlite3
from datetime import datetime, timedelta
from openai import OpenAI

# --- DB Setup ---
conn = sqlite3.connect("diet_feedback.db", check_same_thread=False)
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        date TEXT,
        meal TEXT,
        recipe_name TEXT,
        liked TEXT,
        had_meal TEXT,
        rating INTEGER,
        recipe TEXT
    )
''')

# Ensure all needed columns exist
columns_to_check = ["date", "had_meal", "liked", "recipe_name", "recipe"]
for col in columns_to_check:
    try:
        c.execute(f"ALTER TABLE feedback ADD COLUMN {col} TEXT")
    except sqlite3.OperationalError:
        pass
conn.commit()

# --- App Config ---
st.set_page_config(page_title="Smart Diet Planner", layout="wide", page_icon="🥗")
st.markdown("<h1 style='color:#16a085;'>🥗 Smart Diet & Recipe Planner</h1>", unsafe_allow_html=True)

# --- Sidebar: Select Day (365 Dropdown) ---
base_date = datetime(datetime.now().year, 1, 1)
dates = [(base_date + timedelta(days=i)).strftime("%B %d, %A") for i in range(365)]
selected_day = st.sidebar.selectbox("📅 Select a Day (Week/Month view)", dates)

# --- Sidebar: Select Meal ---
meal_list = ["Breakfast", "Lunch", "Dinner", "Evening Snack", "Late Night Snack"]
selected_meal = st.sidebar.selectbox("🍽️ Select Meal", meal_list)

# --- Smart Button Based on Time ---
current_hour = datetime.now().hour
if current_hour < 11:
    suggested_meal = "Breakfast"
elif 11 <= current_hour < 14:
    suggested_meal = "Lunch"
elif 14 <= current_hour < 18:
    suggested_meal = "Evening Snack"
elif 18 <= current_hour < 21:
    suggested_meal = "Dinner"
else:
    suggested_meal = "Late Night Snack"

generate_label = f"✨ Generate {suggested_meal}" if selected_meal == suggested_meal else f"✨ Generate {selected_meal}"

# --- User Profile ---
with st.expander("👤 Enter Your Info"):
    with st.form("profile_form"):
        col1, col2 = st.columns(2)
        with col1:
            age = st.text_input("Age", "22")
            gender = st.selectbox("Gender", ["Female", "Male", "Other"])
            weight = st.number_input("Current Weight (kg)", 30, 200, 60)
            height = st.number_input("Height (cm)", 120, 220, 165)
        with col2:
            goal_weight = st.number_input("Target Weight (kg)", 30, 200, 55)
            goal = st.selectbox("Goal", ["Lose weight", "Gain weight", "Maintain weight"])
            cuisine = st.selectbox("Cuisine Preference", ["Indian", "Global", "Italian", "Mexican", "Chinese", "Mediterranean", "Keto", "Vegan", "South Indian"])
        save_profile = st.form_submit_button("📂 Save Profile")

if save_profile:
    st.success("✅ Profile saved!")

# --- Cuisine Hints ---
cuisine_hints = {
    "Indian": "Use Indian-style meals like dal, sabzi, khichdi, roti, poha.",
    "Global": "Use global meals like oats, pasta, salads, soups.",
    "Italian": "Use Italian meals like pasta, risotto, minestrone.",
    "Mexican": "Use Mexican meals like tacos, burritos, enchiladas.",
    "Chinese": "Use Chinese meals like noodles, stir fry, dumplings.",
    "Mediterranean": "Use meals like hummus, grilled veggies, pita wraps.",
    "Keto": "Use high-fat low-carb meals like avocado, eggs, grilled meat.",
    "Vegan": "Use fully plant-based meals like tofu, legumes, quinoa.",
    "South Indian": "Use idli, dosa, sambhar, upma, etc."
}

# --- OpenRouter API ---
def call_openrouter(prompt):
    client = OpenAI(
        api_key="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",
        base_url="https://openrouter.ai/api/v1"
    )
    response = client.chat.completions.create(
        model="openai/gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# --- Generate Recipe ---
ingredients = st.text_input(f"🥥 Ingredients for {selected_meal} (comma-separated)")

# Session states
if "recipe_result" not in st.session_state:
    st.session_state.recipe_result = ""
if "submitted" not in st.session_state:
    st.session_state.submitted = False

if st.button(generate_label) and ingredients:
    bmi = weight / ((height / 100) ** 2)
    prompt = f"""
You are a certified dietitian and recipe expert.
User Profile:
- Age: {age}
- Gender: {gender}
- Current Weight: {weight} kg
- Height: {height} cm
- Target Weight: {goal_weight} kg
- Goal: {goal}
- BMI: {bmi:.1f}
Cuisine Preference: {cuisine}
{cuisine_hints[cuisine]}

Generate a {selected_meal} recipe using these ingredients: {ingredients}.
Include:
1. Meal Name
2. Calories
3. Ingredients
4. Cooking Steps
"""
    with st.spinner("Generating..."):
        st.session_state.recipe_result = call_openrouter(prompt)
        st.session_state.submitted = False

# Display recipe and feedback
if st.session_state.recipe_result:
    result = st.session_state.recipe_result
    st.markdown(result, unsafe_allow_html=True)
    recipe_name = result.split('\n')[0].replace("**", "").strip(":").strip()

    if not st.session_state.submitted:
        had_meal = st.radio(f"✅ Did you have your {selected_meal}?", ["No", "Yes"], key="had_meal")
        if had_meal == "Yes":
            liked = st.radio(f"❤️ Did you like the {recipe_name} recipe?", ["Yes", "No"], key="liked_meal")
            rating = st.slider(f"⭐ Rate the {selected_meal} recipe", 1, 5, 3, key="rating_slider")
            if st.button(f"📂 Submit Feedback for {selected_meal}"):
                c.execute('''
                    INSERT INTO feedback (date, meal, recipe_name, liked, had_meal, rating, recipe)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (selected_day, selected_meal, recipe_name, liked, "Yes", rating, result))
                conn.commit()
                st.success("✅ Feedback saved!")
                st.session_state.submitted = True

# --- Daily Progress Summary ---
with st.sidebar:
    st.markdown("📊 **Daily Progress Tracker**")
    c.execute("SELECT meal, had_meal, liked, rating FROM feedback WHERE date=?", (selected_day,))
    data = c.fetchall()
    if data:
        for meal, had_meal, liked, rating in data:
            icon = "✅" if had_meal == "Yes" else "❌"
            heart = "❤️" if liked == "Yes" else "💔"
            stars = "⭐" * int(rating or 0)
            st.markdown(f"{icon} **{meal}** — {heart} {stars}")
    else:
        st.info("No meals tracked yet for this day.")
