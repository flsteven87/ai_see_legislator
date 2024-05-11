import React, { useEffect, useState } from 'react';

function App() {
  const [meetings, setMeetings] = useState([]);

  useEffect(() => {
    fetch('http://localhost:8000/api/meetings/')
      .then(response => response.json())
      .then(data => setMeetings(data));
  }, []);

  return (
    <div>
      <h1>Meetings</h1>
      {meetings.map(meeting => (
        <div key={meeting.id}>
          <h2>{meeting.topic}</h2>
          <p>{meeting.date}</p>
          <p>{meeting.summary}</p>
        </div>
      ))}
    </div>
  );
}

export default App;
