import React, { useState, useRef, useEffect } from 'react';
import { Spinner, Button } from 'react-bootstrap';
import { Camera, User, AlertCircle, Save, X, Move } from 'lucide-react';
import axios from 'axios';

const ImageUpload = ({ currentImageUrl, initialOffsetY = 0, onUploadSuccess }) => {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [offsetY, setOffsetY] = useState(initialOffsetY);
  const [isDragging, setIsDragging] = useState(false);
  const [startY, setStartY] = useState(0);
  const [selectedFile, setSelectedFile] = useState(null);
  
  const fileInputRef = useRef(null);
  const containerRef = useRef(null);

  const API_BASE_URL = 'http://localhost:8000/payroll';
  
  // Final display URL logic
  const displayUrl = previewUrl || (currentImageUrl 
    ? (currentImageUrl.startsWith('http') ? currentImageUrl : `http://localhost:8000${currentImageUrl}`)
    : null);

  useEffect(() => {
    setOffsetY(initialOffsetY);
  }, [initialOffsetY]);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      setError('Please select an image file (JPG/PNG).');
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      setPreviewUrl(reader.result);
      setIsEditing(true);
      setSelectedFile(file);
      setOffsetY(0); // Reset offset for new image
    };
    reader.readAsDataURL(file);
    setError(null);
  };

  const startDrag = (e) => {
    if (!isEditing && !displayUrl) return;
    if (!isEditing) setIsEditing(true); // Auto-enter edit mode if they drag existing photo
    
    setIsDragging(true);
    const clientY = e.type.includes('touch') ? e.touches[0].clientY : e.clientY;
    setStartY(clientY - offsetY);
  };

  const onDrag = (e) => {
    if (!isDragging) return;
    const clientY = e.type.includes('touch') ? e.touches[0].clientY : e.clientY;
    const newY = clientY - startY;
    
    // Optional: Add bounds logic here if we knew the image height
    setOffsetY(newY);
  };

  const stopDrag = () => {
    setIsDragging(false);
  };

  const handleSave = async () => {
    setIsUploading(true);
    setError(null);

    try {
      const token = localStorage.getItem('token');
      let response;

      if (selectedFile) {
        // Upload new file + offset
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('offset_y', offsetY);

        response = await axios.post(`${API_BASE_URL}/employees/profile-picture`, formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
            'Authorization': `Bearer ${token}`
          }
        });
      } else {
        // Just update offset for existing file
        response = await axios.post(`${API_BASE_URL}/employees/profile-picture-settings`, {
          offset_y: offsetY
        }, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
      }

      if (onUploadSuccess) {
        onUploadSuccess(response.data.profile_picture_url || currentImageUrl, offsetY);
      }
      setIsEditing(false);
      setSelectedFile(null);
      setPreviewUrl(null);
    } catch (err) {
      console.error("Save error:", err);
      setError('Failed to save changes.');
    } finally {
      setIsUploading(false);
    }
  };

  const cancelEdit = () => {
    setIsEditing(false);
    setPreviewUrl(null);
    setSelectedFile(null);
    setOffsetY(initialOffsetY);
  };

  return (
    <div className="text-center">
      <div className="position-relative d-inline-block">
        {/* Profile Image Container - Increased to 160px */}
        <div 
          ref={containerRef}
          className="bg-white rounded-circle d-inline-flex align-items-center justify-content-center shadow-lg border border-4 border-white overflow-hidden position-relative"
          style={{ 
            width: '160px', 
            height: '160px', 
            cursor: isDragging ? 'grabbing' : (isEditing ? 'grab' : 'pointer'),
            touchAction: 'none'
          }}
          onMouseDown={startDrag}
          onMouseMove={onDrag}
          onMouseUp={stopDrag}
          onMouseLeave={stopDrag}
          onTouchStart={startDrag}
          onTouchMove={onDrag}
          onTouchEnd={stopDrag}
        >
          {displayUrl ? (
            <img 
              src={displayUrl} 
              alt="Profile" 
              className="w-100 position-absolute" 
              style={{ 
                height: 'auto',
                top: `${offsetY}px`,
                pointerEvents: 'none',
                userSelect: 'none'
              }}
              onError={(e) => { e.target.src = ''; }}
            />
          ) : (
            <User size={80} style={{ color: '#A8867F' }} />
          )}

          {/* Edit Overlay (only when not editing) */}
          {!isEditing && (
            <div 
              className="position-absolute top-0 start-0 w-100 h-100 d-flex flex-column align-items-center justify-content-center bg-dark bg-opacity-25 opacity-0 hover-opacity-100 transition-all"
              style={{ transition: 'opacity 0.2s', zIndex: 2 }}
              onMouseDown={(e) => e.stopPropagation()} // Prevent drag from starting on click
              onClick={(e) => {
                e.stopPropagation();
                fileInputRef.current?.click();
              }}
            >
              <Camera size={32} className="text-white mb-1" />
              <span className="text-white small fw-bold">Change Photo</span>
            </div>
          )}

          {/* Move Indicator (when editing) */}
          {isEditing && !isDragging && (
            <div className="position-absolute bottom-0 w-100 bg-dark bg-opacity-50 text-white py-1" style={{ fontSize: '10px' }}>
              <Move size={12} className="me-1" /> Drag to position
            </div>
          )}

          {/* Loading Spinner */}
          {isUploading && (
            <div className="position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center bg-white bg-opacity-75" style={{ zIndex: 10 }}>
              <Spinner animation="border" style={{ color: '#A8867F' }} />
            </div>
          )}
        </div>

        {/* Hidden File Input */}
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept="image/*"
          className="d-none"
        />

        {/* Error Message */}
        {error && (
          <div className="position-absolute start-50 translate-middle-x mt-2 w-100" style={{ zIndex: 5 }}>
            <div className="bg-danger text-white small px-3 py-1 rounded-pill d-flex align-items-center justify-content-center gap-1 shadow-sm mx-auto" style={{ width: 'fit-content' }}>
              <AlertCircle size={12} />
              <span style={{ fontSize: '11px' }}>{error}</span>
            </div>
          </div>
        )}
      </div>

      {/* Action Buttons (Visible only in edit mode) */}
      {isEditing && !isUploading && (
        <div className="mt-3 d-flex justify-content-center gap-2 animate-fade-in">
          <Button 
            variant="light" 
            size="sm" 
            className="rounded-pill px-3 d-flex align-items-center gap-1 border shadow-sm"
            onClick={cancelEdit}
          >
            <X size={14} /> Cancel
          </Button>
          <Button 
            variant="primary" 
            size="sm" 
            className="rounded-pill px-4 d-flex align-items-center gap-1 shadow-sm"
            style={{ backgroundColor: '#A8867F', borderColor: '#A8867F' }}
            onClick={handleSave}
          >
            <Save size={14} /> Save Profile
          </Button>
        </div>
      )}

      <style>{`
        .hover-opacity-100:hover { opacity: 1 !important; }
        .transition-all { transition: all 0.2s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        .animate-fade-in { animation: fadeIn 0.3s ease-out; }
      `}</style>
    </div>
  );
};

export default ImageUpload;
