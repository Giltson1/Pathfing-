const requestOptyions = { 
    method: "GET",
    redirect:"follow"
};

fetch = ("https://api.geoapify.com/v1/geocode/autocomplete?text=query&limit=5&format=json&apiKey=YOUR_API_KEY", requestOptions)
  .then((response) => response.text())
  .then((result) => console.log(result))
  .catch((error) => console.error(error));

// Entre key 
document.getElementById("startInput").addEventListener('keydown', (e) =>
{ if (e.key === "enter") runphfinding(); });

document.getElementById("endInput").addEventListener('keydown', (e) =>
{ if (e.key === "enter") runphfinding(); });