import React, { useState, useEffect } from "react";

// 🌾 Backend URL
const API_BASE = "http://127.0.0.1:8000";

export default function App() {
  // ------------------ State ------------------
  const [lang, setLang] = useState("en");
  const [isAuth, setIsAuth] = useState(false);
  const [user, setUser] = useState(null);

  // Auth
  const [authMode, setAuthMode] = useState("login"); // "login" | "signup"
  const [authForm, setAuthForm] = useState({ username: "", password: "" });

  // Weather
  const [district, setDistrict] = useState("Ludhiana");
  const [weather, setWeather] = useState(null);

  // Mandi
  const [crop, setCrop] = useState("Wheat");
  const [mandiPrice, setMandiPrice] = useState(null);

  // Crop Recommendation
  const [inputs, setInputs] = useState({
    N: 50,
    P: 50,
    K: 50,
    temp: 28,
    humidity: 60,
    ph: 6.5,
    rainfall: 100,
  });
  const [recommendedCrop, setRecommendedCrop] = useState(null);

  // Chatbot
  const [chatQuery, setChatQuery] = useState("");
  const [chatReply, setChatReply] = useState("");

  // Voice Query
  const [voiceReply, setVoiceReply] = useState(null);

  // ------------------ API Calls ------------------
  const handleAuth = async () => {
    const route = authMode === "login" ? "/login" : "/signup";
    const res = await fetch(API_BASE + route, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...authForm, pref_lang: lang }),
    });
    const data = await res.json();
    if (data.success) {
      setIsAuth(true);
      setUser(authForm.username);
    } else {
      alert("Failed. Try again.");
    }
  };

  const fetchWeather = async () => {
    const res = await fetch(`${API_BASE}/weather?district=${district}`);
    const data = await res.json();
    setWeather(data.latest);
  };

  const fetchMandiPrice = async () => {
    const res = await fetch(
      `${API_BASE}/mandi-price?crop=${crop}&state=Punjab`
    );
    const data = await res.json();
    setMandiPrice(data.price);
  };

  const fetchRecommendation = async () => {
    const res = await fetch(`${API_BASE}/recommend-crop`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(inputs),
    });
    const data = await res.json();
    setRecommendedCrop(data.crop);
  };

  const sendChat = async () => {
    const res = await fetch(`${API_BASE}/chatbot`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: chatQuery,
        district,
        crop,
        ...inputs,
        lang,
      }),
    });
    const data = await res.json();
    setChatReply(data.reply);
    if (data.audio_url) {
      setVoiceReply(API_BASE + data.audio_url);
    }
  };

  // ------------------ UI ------------------
  if (!isAuth) {
    return (
      <div style={styles.container}>
        <h1 style={styles.title}>🌾 Smart Crop Advisory</h1>
        <div style={styles.card}>
          <h2>{authMode === "login" ? "Login" : "Signup"}</h2>
          <input
            style={styles.input}
            placeholder="Username"
            value={authForm.username}
            onChange={(e) =>
              setAuthForm({ ...authForm, username: e.target.value })
            }
          />
          <input
            style={styles.input}
            type="password"
            placeholder="Password"
            value={authForm.password}
            onChange={(e) =>
              setAuthForm({ ...authForm, password: e.target.value })
            }
          />
          <button style={styles.button} onClick={handleAuth}>
            {authMode === "login" ? "Login" : "Signup"}
          </button>
          <p>
            {authMode === "login" ? "No account?" : "Already a user?"}{" "}
            <span
              style={{ color: "blue", cursor: "pointer" }}
              onClick={() =>
                setAuthMode(authMode === "login" ? "signup" : "login")
              }
            >
              {authMode === "login" ? "Signup" : "Login"}
            </span>
          </p>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <h1 style={styles.title}>🌾 Welcome, {user}</h1>

      {/* Weather */}
      <div style={styles.card}>
        <h2>☁️ Weather in {district}</h2>
        <select
          style={styles.input}
          value={district}
          onChange={(e) => setDistrict(e.target.value)}
        >
          <option>Ludhiana</option>
          <option>Amritsar</option>
          <option>Patiala</option>
          <option>Bathinda</option>
          <option>Ferozepur</option>
          <option>Hoshiarpur</option>
          <option>Jalandhar</option>
        </select>
        <button style={styles.button} onClick={fetchWeather}>
          Get Weather
        </button>
        {weather && (
          <p>
            🌡 {weather.temperature}°C | 💧 {weather.humidity}% | 🌧{" "}
            {weather.rainfall} mm
          </p>
        )}
      </div>

      {/* Mandi Price */}
      <div style={styles.card}>
        <h2>💹 Mandi Price</h2>
        <select
          style={styles.input}
          value={crop}
          onChange={(e) => setCrop(e.target.value)}
        >
          <option>Wheat</option>
          <option>Rice</option>
          <option>Maize</option>
          <option>Cotton</option>
          <option>Pulses</option>
        </select>
        <button style={styles.button} onClick={fetchMandiPrice}>
          Get Price
        </button>
        {mandiPrice && <p>Current Price: ₹{mandiPrice} per quintal</p>}
      </div>

      {/* Crop Recommendation */}
      <div style={styles.card}>
        <h2>🌱 Crop Recommendation</h2>
        <div>
          {["N", "P", "K", "temp", "humidity", "ph", "rainfall"].map((key) => (
            <input
              key={key}
              style={styles.input}
              type="number"
              placeholder={key}
              value={inputs[key]}
              onChange={(e) =>
                setInputs({ ...inputs, [key]: parseFloat(e.target.value) })
              }
            />
          ))}
        </div>
        <button style={styles.button} onClick={fetchRecommendation}>
          Recommend Crop
        </button>
        {recommendedCrop && <p>Recommended Crop: 🌾 {recommendedCrop}</p>}
      </div>

      {/* Chatbot */}
      <div style={styles.card}>
        <h2>🤖 Ask Advisor</h2>
        <input
          style={styles.input}
          placeholder="Ask about weather, irrigation, soil..."
          value={chatQuery}
          onChange={(e) => setChatQuery(e.target.value)}
        />
        <button style={styles.button} onClick={sendChat}>
          Send
        </button>
        {chatReply && <p>Advisor: {chatReply}</p>}
        {voiceReply && (
          <audio controls src={voiceReply} style={{ marginTop: "10px" }} />
        )}
      </div>
    </div>
  );
}

// ------------------ Styles ------------------
const styles = {
  container: {
    maxWidth: "600px",
    margin: "0 auto",
    padding: "20px",
    fontFamily: "Arial, sans-serif",
  },
  title: {
    textAlign: "center",
    color: "green",
  },
  card: {
    background: "#f9f9f9",
    padding: "15px",
    borderRadius: "12px",
    marginBottom: "20px",
    boxShadow: "0 2px 5px rgba(0,0,0,0.1)",
  },
  input: {
    width: "100%",
    padding: "10px",
    margin: "5px 0",
    borderRadius: "8px",
    border: "1px solid #ccc",
  },
  button: {
    width: "100%",
    padding: "10px",
    marginTop: "10px",
    background: "green",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontWeight: "bold",
  },
};
