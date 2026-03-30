import React, { useState } from 'react';
import AttendanceTable from '../components/dashboard/AttendanceTable';
import MonthlyAttendanceSheet from '../components/dashboard/MonthlyAttendanceSheet';
import 'bootstrap/dist/css/bootstrap.min.css';
import { List, Calendar } from 'lucide-react';

const Attendance = () => {
  const [view, setView] = useState('logs'); // 'logs' or 'sheet'

  return (
    <div className="main-content-sia">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="fw-bold m-0">Attendance Monitoring</h2>
        
        {/* Toggle Switch */}
        <div className="bg-white p-1 rounded-pill shadow-sm d-flex gap-1">
          <button 
            onClick={() => setView('logs')}
            className={`btn rounded-pill px-4 d-flex align-items-center gap-2 border-0 ${view === 'logs' ? 'shadow-sm' : ''}`}
            style={{ 
              backgroundColor: view === 'logs' ? '#D29191' : 'transparent',
              color: view === 'logs' ? 'white' : '#A08E8E',
              fontWeight: '600',
              fontSize: '13px',
              transition: 'all 0.3s ease'
            }}
          >
            <List size={16} /> Real-time Logs
          </button>
          <button 
            onClick={() => setView('sheet')}
            className={`btn rounded-pill px-4 d-flex align-items-center gap-2 border-0 ${view === 'sheet' ? 'shadow-sm' : ''}`}
            style={{ 
              backgroundColor: view === 'sheet' ? '#D29191' : 'transparent',
              color: view === 'sheet' ? 'white' : '#A08E8E',
              fontWeight: '600',
              fontSize: '13px',
              transition: 'all 0.3s ease'
            }}
          >
            <Calendar size={16} /> Monthly Timesheet
          </button>
        </div>
      </div>

      <div className="bg-white p-4 rounded-4 shadow-sm">
        {view === 'logs' ? <AttendanceTable showFilters={true} defaultPeriod="yesterday" /> : <MonthlyAttendanceSheet />}
      </div>
    </div>
  );
};

export default Attendance;
