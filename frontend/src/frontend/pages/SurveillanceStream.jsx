import { useState, useEffect, useCallback } from 'react';
import { Bell } from 'lucide-react';

// Toast notification component
const Toast = ({ message, onClose }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose();
    }, 5000);
    
    return () => clearTimeout(timer);
  }, [onClose]);
  
  return (
    <div className="fixed bottom-4 right-4 bg-red-600 text-white p-4 rounded-lg shadow-lg flex items-center gap-2 z-50 animate-bounce">
      <Bell size={24} />
      <p>{message}</p>
    </div>
  );
};

// Main surveillance component
export default function SurveillanceStream() {
  const [streamUrl, setStreamUrl] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [notification, setNotification] = useState(null);
  const [detections, setDetections] = useState([]);
  
  // Configuration - adjust these values based on your setup
  const FLASK_SERVER = 'http://192.168.1.100:5000'; // Change to your RPi's IP address
  const STREAM_ENDPOINT = '/video_feed';
  const DETECTIONS_ENDPOINT = '/api/detections';
  const POLLING_INTERVAL = 2000; // Check for new detections every 2 seconds
  
  // Initialize stream
  useEffect(() => {
    setStreamUrl(`${FLASK_SERVER}${STREAM_ENDPOINT}`);
    checkServerConnection();
  }, []);
  
  // Check if the Flask server is reachable
  const checkServerConnection = useCallback(async () => {
    try {
      const response = await fetch(`${FLASK_SERVER}/ping`, { timeout: 3000 });
      if (response.ok) {
        setIsConnected(true);
      } else {
        setIsConnected(false);
      }
    } catch (error) {
      console.error('Failed to connect to surveillance server:', error);
      setIsConnected(false);
    }
  }, []);
  
  // Poll for new human detections
  useEffect(() => {
    let interval;
    
    if (isConnected) {
      interval = setInterval(async () => {
        try {
          const response = await fetch(`${FLASK_SERVER}${DETECTIONS_ENDPOINT}`);
          if (response.ok) {
            const data = await response.json();
            
            // Check if we have new detections
            if (data.detections && data.detections.length > 0) {
              // Get only new detections we haven't seen
              const lastDetectionTime = detections.length > 0 ? 
                new Date(detections[0].timestamp) : new Date(0);
              
              const newDetections = data.detections.filter(detection => 
                new Date(detection.timestamp) > lastDetectionTime
              );
              
              if (newDetections.length > 0) {
                setDetections(prev => [...newDetections, ...prev].slice(0, 50)); // Keep last 50 detections
                
                // Show notification for human detection
                if (newDetections.some(d => d.class === 'person')) {
                  setNotification(`Human detected at ${new Date().toLocaleTimeString()}`);
                }
              }
            }
          }
        } catch (error) {
          console.error('Error fetching detection data:', error);
        }
      }, POLLING_INTERVAL);
    }
    
    return () => clearInterval(interval);
  }, [isConnected, detections]);
  
  // Handle the notification close
  const handleCloseNotification = () => {
    setNotification(null);
  };
  
  return (
    <div className="flex flex-col items-center w-full max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold mb-4">Surveillance Stream</h2>
      
      {/* Connection status */}
      <div className={`mb-4 flex items-center ${isConnected ? 'text-green-500' : 'text-red-500'}`}>
        <div className={`w-3 h-3 rounded-full mr-2 ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></div>
        <span>{isConnected ? 'Connected' : 'Disconnected'}</span>
      </div>
      
      {/* Video stream container */}
      <div className="relative w-full aspect-video bg-gray-900 rounded-lg overflow-hidden">
        {isConnected ? (
          <img 
            src={streamUrl} 
            alt="Live surveillance stream" 
            className="w-full h-full object-contain"
          />
        ) : (
          <div className="flex items-center justify-center w-full h-full">
            <p className="text-white">Attempting to connect to surveillance camera...</p>
          </div>
        )}
      </div>
      
      {/* Recent detections list */}
      <div className="w-full mt-6">
        <h3 className="text-xl font-semibold mb-2">Recent Human Detections</h3>
        <div className="bg-gray-100 p-4 rounded-lg max-h-64 overflow-y-auto">
          {detections.filter(d => d.class === 'person').length > 0 ? (
            <ul className="divide-y divide-gray-300">
              {detections
                .filter(d => d.class === 'person')
                .map((detection, index) => (
                  <li key={index} className="py-2">
                    <span className="font-medium">
                      {new Date(detection.timestamp).toLocaleString()}
                    </span>
                    <span className="ml-2">
                      {detection.confidence ? 
                        `(Confidence: ${Math.round(detection.confidence * 100)}%)` : 
                        ''}
                    </span>
                  </li>
                ))}
            </ul>
          ) : (
            <p className="text-gray-500">No human detections yet</p>
          )}
        </div>
      </div>
      
      {/* Toast notification */}
      {notification && (
        <Toast message={notification} onClose={handleCloseNotification} />
      )}
    </div>
  );
}