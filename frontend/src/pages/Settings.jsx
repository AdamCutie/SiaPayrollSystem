import React from 'react';
import { Card, Form, Button, Row, Col } from 'react-bootstrap';
import TopBar from '../components/layout/TopBar';

const Settings = () => {
  return (
    <div className="main-content-sia">
      <TopBar title="Settings" />

      <Card className="border-0 shadow-sm rounded-4 p-4">
        <Card.Body>
          <h5 className="fw-bold mb-4">Payroll Configuration</h5>
          
          <Form>
            <Row>
              <Col md={4}>
                <Form.Group className="mb-3" controlId="formAverageSalary">
                  <Form.Label>Average Salary</Form.Label>
                  <Form.Control type="number" placeholder="Enter average salary" defaultValue="500" />
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group className="mb-3" controlId="formDeductionLate">
                  <Form.Label>Deduction Per Hour (Late)</Form.Label>
                  <Form.Control type="number" placeholder="Enter deduction for lateness" defaultValue="600" />
                </Form.Group>
              </Col>
              <Col md={4}>
                <Form.Group className="mb-3" controlId="formDeductionAbsent">
                  <Form.Label>Deduction Per Hour (Absent)</Form.Label>
                  <Form.Control type="number" placeholder="Enter deduction for absence" defaultValue="600" />
                </Form.Group>
              </Col>
            </Row>
            <div className="mt-3 text-end">
              <Button variant="primary" type="submit">
                Save Changes
              </Button>
            </div>
          </Form>
        </Card.Body>
      </Card>
    </div>
  );
};

export default Settings;
