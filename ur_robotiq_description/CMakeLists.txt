cmake_minimum_required(VERSION 3.5)
project(ur_robotiq_description)

# Find dependencies
find_package(ament_cmake REQUIRED)
find_package(ur_description REQUIRED)
find_package(robotiq_description REQUIRED)

# Create an interface library target
add_library(${PROJECT_NAME} INTERFACE)

# Link the required components to the target
target_link_libraries(${PROJECT_NAME} INTERFACE
  ur_description::ur_description
  robotiq_description::robotiq_description
)

# INSTALL

# Install the urdf files
install(DIRECTORY urdf/
  DESTINATION share/${PROJECT_NAME}/urdf)

# Install the config files
install(DIRECTORY config/
  DESTINATION share/${PROJECT_NAME}/config)

# Install the launch files
install(DIRECTORY launch/
  DESTINATION share/${PROJECT_NAME}/launch
)

# ament package
ament_package()