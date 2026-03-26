import React from 'react';
import AttendanceTable from '../components/dashboard/AttendanceTable';
import 'bootstrap/dist/css/bootstrap.min.css';

const Attendance = () => {
  return (
    <div className="main-content-sia">
      <h2 className="fw-bold mb-4">Attendance</h2>
      <div className="bg-white p-4 rounded-4 shadow-sm">
        <AttendanceTable />
      </div>
    </div>
  );
};

export default Attendance;
